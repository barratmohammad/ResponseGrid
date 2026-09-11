"""Builds the .pipe graphs.

Two shapes, SAME agents / SAME instructions / SAME data -- only the topology differs:

  parallel:   webhook -> 5 specialists (independent branches) -> commander -> response_json
  sequential: webhook -> s1 -> s2 -> s3 -> s4 -> s5 -> commander -> response_json

That makes the benchmark honest: the difference measured is concurrency, not workload.

Shape facts verified against the engine and a real upstream example pipe:
  * `control` lives INSIDE a component and its direction is INVERTED -- the
    llm/tool/memory node declares `from: <agent_id>`, i.e. provider -> consumer.
  * LLM api keys nest under a key named after the selected profile.
  * db_hotdata takes flat dotted `hotdata.*` config keys (prefix "hotdata") and
    falls back to HOTDATA_API_KEY / HOTDATA_WORKSPACE from the engine's env.
  * `source` passed to use() must be the ID of the entry component.
"""
from __future__ import annotations
import json
from pathlib import Path

from agents import AGENTS, COMMANDER_ID, COMMANDER_INSTRUCTIONS, ORDER
import config

ROOT = Path(__file__).resolve().parents[1]
PIPE_DIR = ROOT / "pipes"
SOURCE_ID = "incident_feed"
RESPONSE_ID = "plan_out"
PLAN_LANE = "plan"


KEY_PLACEHOLDER = "${ANTHROPIC_API_KEY}"


def _llm(node_id: str, owner: str, profile: str, apikey: str | None = None) -> dict:
    """An Anthropic node bound as the `llm` channel of `owner`.

    The engine does NOT expand ${VAR} in pipe config (that is a CLI/extension
    feature), so a placeholder reaches the node verbatim and fails its `sk-ant`
    format check. We therefore inject the real key when building the pipe we
    execute, and keep the placeholder in the reference .pipe files we publish.
    """
    key = apikey or KEY_PLACEHOLDER
    return {
        "id": node_id, "provider": "llm_anthropic",
        "name": f"Claude ({profile})",
        # key nests under the profile name (verified against a real upstream pipe);
        # the flat form is set too since builds differ on which they read.
        "config": {"profile": profile,
                   profile: {"apikey": key},
                   "apikey": key,
                   "parameters": {}},
        "control": [{"classType": "llm", "from": owner}],
    }


def _memory(node_id: str, owner: str) -> dict:
    return {"id": node_id, "provider": "memory_internal",
            "config": {"type": "memory_internal", "parameters": {}},
            "control": [{"classType": "memory", "from": owner}]}


def _hotdata(node_id: str, owner: str, database_id: str, table_hint: str,
             hd_key: str | None = None, hd_ws: str | None = None) -> dict:
    """Per-agent Hotdata database, bound as a `tool` of `owner`.

    Config keys are UNPREFIXED. The node declares its fields as `hotdata.*` for
    the UI form, but the engine strips that namespace before handing the dict to
    the node -- its source reads cfg.get('apikey'), cfg.get('database_id'), etc.
    Writing `hotdata.database_id` therefore leaves database_id empty, and the node
    silently provisions its OWN throwaway database instead of attaching to ours.

    Supplying database_id makes the node ATTACH, and an attached database is never
    deleted by the node -- our backend owns create -> load -> destroy.
    allow_execute lets the agent run raw read-only SQL (the SQL surface rejects
    writes regardless; this gate only guards expensive scans).
    """
    cfg = {
        "profile": "default",
        "apikey": hd_key or "${HOTDATA_API_KEY}",
        "workspace_id": hd_ws or "${HOTDATA_WORKSPACE_ID}",
        "database_id": database_id,
        "allow_execute": True,
        "allow_destructive_load": False,
        "db_description": table_hint,
        "max_execute_rows": 2000,
        "job_timeout_secs": 60,
        "max_attempts": 2,
        "parameters": {},
    }
    return {"id": node_id, "provider": "db_hotdata", "name": f"Hotdata {owner}",
            "config": cfg, "control": [{"classType": "tool", "from": owner}]}


def _specialist(agent_id: str, database_id: str, inputs: list[dict],
                secrets: dict | None = None) -> list[dict]:
    a = AGENTS[agent_id]
    hint = (f"Tables in default.main: {', '.join(a.tables)}. "
            f"All rows are simulated exercise data. Domain: {a.domain}.")
    return [
        {"id": agent_id, "provider": "agent_rocketride",
         "name": a.label,
         "config": {"agent_description": f"{a.label} specialist for {a.domain}",
                    "instructions": a.agent_instructions(),
                    "max_waves": config.MAX_WAVES,
                    "agent_rocketride": {"profile": "default"},
                    "parameters": {}},
         "input": inputs},
        _llm(f"llm_{agent_id}", agent_id, config.SPECIALIST_PROFILE, (secrets or {}).get("anthropic")),
        _memory(f"mem_{agent_id}", agent_id),
        _hotdata(f"hd_{agent_id}", agent_id, database_id, hint,
                 (secrets or {}).get("hotdata_key"), (secrets or {}).get("hotdata_ws")),
    ]


def _commander(inputs: list[dict], secrets: dict | None = None,
               findings_block: str | None = None) -> list[dict]:
    return [
        {"id": COMMANDER_ID, "provider": "agent_rocketride",
         "name": "INCIDENT COMMANDER",
         "config": {"agent_description": "Merges specialist findings into one incident command plan",
                    # The findings ride in `instructions` rather than on the questions
                    # lane: lane data does not reach an agent as its query, so a
                    # commander fed that way reports "no findings received" and
                    # invents conflicts. instructions is config and always arrives.
                    "instructions": (COMMANDER_INSTRUCTIONS + [findings_block]
                                     if findings_block else COMMANDER_INSTRUCTIONS),
                    "max_waves": 1,          # pure synthesis: one pass, no tool loop
                    "agent_rocketride": {"profile": "default"},
                    "parameters": {}},
         "input": inputs},
        _llm(f"llm_{COMMANDER_ID}", COMMANDER_ID, config.COMMANDER_PROFILE,
             (secrets or {}).get("anthropic")),
        _memory(f"mem_{COMMANDER_ID}", COMMANDER_ID),
    ]


def _source() -> dict:
    return {"id": SOURCE_ID, "provider": "webhook", "name": "Incident feed",
            "config": {"type": "webhook", "mode": "Source", "hideForm": True, "parameters": {}}}


def _response(from_id: str, lane_name: str, node_id: str, label: str) -> dict:
    """A sink per producer. Each distinct laneName becomes its own key in the
    result that send() returns, so we get every specialist's JSON back plus the
    commander's plan from one call -- no flow-event scraping."""
    return {"id": node_id, "provider": "response", "name": label,
            "config": {"laneName": lane_name, "parameters": {}},
            "input": [{"lane": "answers", "from": from_id}]}


def build(mode: str, db_ids: dict[str, str], agent_ids: list[str] | None = None,
          secrets: dict | None = None) -> dict:
    """mode: 'parallel' | 'sequential'. db_ids maps agent_id -> Hotdata database id."""
    ids = agent_ids or ORDER
    if secrets is None:
        secrets = {"anthropic": config.ANTHROPIC_API_KEY or None,
                   "hotdata_key": config.HOTDATA_API_KEY or None,
                   "hotdata_ws": config.HOTDATA_WORKSPACE_ID or None}
    comps: list[dict] = [_source()]

    _ = fan_in_unused = None
    if mode == "parallel":
        # Every specialist reads the source directly => independent branches the
        # engine runs concurrently across threads.
        for aid in ids:
            comps += _specialist(aid, db_ids.get(aid, ""), [{"lane": "questions", "from": SOURCE_ID}], secrets)
        pass
    elif mode == "sequential":
        # Each specialist consumes the previous one's answers => strictly serial.
        prev, prev_lane = SOURCE_ID, "questions"
        for aid in ids:
            comps += _specialist(aid, db_ids.get(aid, ""), [{"lane": prev_lane, "from": prev}], secrets)
            prev, prev_lane = aid, "answers"
        pass
    else:
        raise ValueError(f"unknown mode {mode!r}")

    # One sink per specialist. The commander is NOT in this graph: an agent node
    # processes each arriving object independently, so a 5-way fan-in makes it run
    # five times and the last answer wins. The merge is its own wave (build_merge).
    for aid in ids:
        comps.append(_response(aid, aid, f"out_{aid}", f"{AGENTS[aid].label} result"))
    return {
        "name": f"ResponseGrid ({mode})",
        "description": (
            ("Parallel emergency incident command: 5 specialists run as independent "
             "branches, each with its own Hotdata database, merged by an incident "
             "commander (see responsegrid_merge.pipe).")
            if mode == "parallel" else
            ("Chained variant kept for reference only. NOT the benchmark baseline: an "
             "agent fed the previous agent's answers lane does not treat that data as "
             "its query and no-ops, so the real baseline runs the single-agent parallel "
             "graph once per specialist, serially. See README.")),
        "version": 1,
        "source": SOURCE_ID,
        "components": comps,
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


def write_reference_pipes() -> list[Path]:
    """Emit submittable .pipe files with placeholder db ids."""
    PIPE_DIR.mkdir(exist_ok=True)
    out = []
    placeholder = {a: f"${{HOTDATA_DB_{a.upper()}}}" for a in ORDER}
    redacted: dict = {}          # -> placeholders, so no key is ever written to disk
    for mode in ("parallel", "sequential"):
        p = PIPE_DIR / f"responsegrid_{mode}.pipe"
        p.write_text(json.dumps(build(mode, placeholder, secrets=redacted), indent=2) + "\n")
        out.append(p)
    p = PIPE_DIR / "responsegrid_merge.pipe"
    p.write_text(json.dumps(build_merge(secrets=redacted), indent=2) + "\n")
    out.append(p)
    return out


if __name__ == "__main__":
    for p in write_reference_pipes():
        d = json.loads(p.read_text())
        print(f"{p.name:34} components={len(d['components']):3d} source={d['source']}")


def build_merge(findings: dict | list | None = None,
                secrets: dict | None = None) -> dict:
    """The merge wave: one commander that receives ALL five results together.

    Kept as a separate graph on purpose. agent_rocketride handles each object
    arriving on its input lane as its own unit of work, so wiring five specialist
    `answers` lanes into one agent runs it five times and the last answer wins
    rather than producing a synthesis. Passing the five results in a single
    payload guarantees the commander sees the whole picture once.
    """
    if secrets is None:
        secrets = {"anthropic": config.ANTHROPIC_API_KEY or None}
    block = None
    if findings is not None:
        block = ("Here are the specialist findings to merge. This is your input data; "
                 "merge exactly these and do not invent findings:\n"
                 + json.dumps(findings, default=str))
    comps = [_source()]
    comps += _commander([{"lane": "questions", "from": SOURCE_ID}], secrets, block)
    comps.append(_response(COMMANDER_ID, PLAN_LANE, RESPONSE_ID, "Incident Command Plan"))
    return {"name": "ResponseGrid (merge wave)",
            "description": "Incident Commander merges the specialists' findings into one plan.",
            "version": 1, "source": SOURCE_ID, "components": comps,
            "viewport": {"x": 0, "y": 0, "zoom": 1}}
