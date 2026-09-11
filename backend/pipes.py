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


def _llm(node_id: str, owner: str, profile: str) -> dict:
    """An Anthropic node bound as the `llm` channel of `owner`."""
    return {
        "id": node_id, "provider": "llm_anthropic",
        "name": f"Claude ({profile})",
        "config": {"profile": profile,
                   # key nests under the profile name (verified against a real pipe)
                   profile: {"apikey": "${ANTHROPIC_API_KEY}"},
                   "apikey": "${ANTHROPIC_API_KEY}",
                   "parameters": {}},
        "control": [{"classType": "llm", "from": owner}],
    }


def _memory(node_id: str, owner: str) -> dict:
    return {"id": node_id, "provider": "memory_internal",
            "config": {"type": "memory_internal", "parameters": {}},
            "control": [{"classType": "memory", "from": owner}]}


def _hotdata(node_id: str, owner: str, database_id: str, table_hint: str) -> dict:
    """Per-agent Hotdata database, bound as a `tool` of `owner`.

    database_id is supplied by us, so the node ATTACHES rather than creating its
    own -- and an attached database is never deleted by the node. Our backend owns
    create -> load -> destroy so the lifecycle is explicit and observable.
    """
    cfg = {
        "profile": "default",
        # nested form
        "hotdata": {
            "apikey": "${HOTDATA_API_KEY}", "workspace_id": "${HOTDATA_WORKSPACE_ID}",
            "database_id": database_id, "allow_execute": True,
            "allow_destructive_load": False, "db_description": table_hint,
            "max_execute_rows": 2000, "job_timeout_secs": 60, "max_attempts": 2,
        },
        # flat dotted form (the node declares its fields this way)
        "hotdata.apikey": "${HOTDATA_API_KEY}",
        "hotdata.workspace_id": "${HOTDATA_WORKSPACE_ID}",
        "hotdata.database_id": database_id,
        "hotdata.allow_execute": True,
        "hotdata.allow_destructive_load": False,
        "hotdata.db_description": table_hint,
        "hotdata.max_execute_rows": 2000,
        "hotdata.job_timeout_secs": 60,
        "hotdata.max_attempts": 2,
        "parameters": {},
    }
    return {"id": node_id, "provider": "db_hotdata", "name": f"Hotdata {owner}",
            "config": cfg, "control": [{"classType": "tool", "from": owner}]}


def _specialist(agent_id: str, database_id: str, inputs: list[dict]) -> list[dict]:
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
        _llm(f"llm_{agent_id}", agent_id, config.SPECIALIST_PROFILE),
        _memory(f"mem_{agent_id}", agent_id),
        _hotdata(f"hd_{agent_id}", agent_id, database_id, hint),
    ]


def _commander(inputs: list[dict]) -> list[dict]:
    return [
        {"id": COMMANDER_ID, "provider": "agent_rocketride",
         "name": "INCIDENT COMMANDER",
         "config": {"agent_description": "Merges specialist findings into one incident command plan",
                    "instructions": COMMANDER_INSTRUCTIONS,
                    "max_waves": 1,          # pure synthesis: one pass, no tool loop
                    "agent_rocketride": {"profile": "default"},
                    "parameters": {}},
         "input": inputs},
        _llm(f"llm_{COMMANDER_ID}", COMMANDER_ID, config.COMMANDER_PROFILE),
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


def build(mode: str, db_ids: dict[str, str], agent_ids: list[str] | None = None) -> dict:
    """mode: 'parallel' | 'sequential'. db_ids maps agent_id -> Hotdata database id."""
    ids = agent_ids or ORDER
    comps: list[dict] = [_source()]

    if mode == "parallel":
        # Every specialist reads the source directly => independent branches the
        # engine runs concurrently across threads.
        for aid in ids:
            comps += _specialist(aid, db_ids.get(aid, ""), [{"lane": "questions", "from": SOURCE_ID}])
        fan_in = [{"lane": "answers", "from": aid} for aid in ids]
    elif mode == "sequential":
        # Each specialist consumes the previous one's answers => strictly serial.
        prev, prev_lane = SOURCE_ID, "questions"
        for aid in ids:
            comps += _specialist(aid, db_ids.get(aid, ""), [{"lane": prev_lane, "from": prev}])
            prev, prev_lane = aid, "answers"
        fan_in = [{"lane": "answers", "from": ids[-1]}]
    else:
        raise ValueError(f"unknown mode {mode!r}")

    comps += _commander(fan_in)
    # One sink per specialist so their raw JSON comes back alongside the plan.
    for aid in ids:
        comps.append(_response(aid, aid, f"out_{aid}", f"{AGENTS[aid].label} result"))
    comps.append(_response(COMMANDER_ID, PLAN_LANE, RESPONSE_ID, "Incident Command Plan"))
    return {
        "name": f"ResponseGrid ({mode})",
        "description": ("Parallel" if mode == "parallel" else "Sequential")
                       + " emergency incident command: 5 specialists, each with its own "
                         "Hotdata database, merged by an incident commander.",
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
    for mode in ("parallel", "sequential"):
        p = PIPE_DIR / f"responsegrid_{mode}.pipe"
        p.write_text(json.dumps(build(mode, placeholder), indent=2) + "\n")
        out.append(p)
    return out


if __name__ == "__main__":
    for p in write_reference_pipes():
        d = json.loads(p.read_text())
        print(f"{p.name:34} components={len(d['components']):3d} source={d['source']}")
