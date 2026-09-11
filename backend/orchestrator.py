"""Run lifecycle.

The explicit Hotdata lifecycle -- create -> load -> index -> query -> destroy --
is owned HERE rather than left to the db_hotdata node, so that every step emits an
observable event and each agent's database is preloaded with only its own slice.

Timing is measured, never assumed: wall clock around the pipeline for the run,
and per-agent spans derived from the engine's own flow events where available,
falling back to our observed first/last activity per agent.
"""
from __future__ import annotations
import asyncio, json, time, uuid
from datetime import datetime, timezone
from typing import Any

from rocketride import RocketRideClient

import config, pipes
from agents import AGENTS, COMMANDER_ID, INJECTION_IMPACT, ORDER
from events import BUS
from hotdata import HotdataClient, HotdataError
from schemas import validate_plan, validate_specialist
from scenarios import palisades
from telemetry import TelemetryStore

SCENARIOS = {palisades.SCENARIO_ID: palisades}
RUNS: dict[str, dict] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def _compact(agent_id: str, res: dict) -> dict:
    """Squeeze a specialist result down to what the commander needs.

    Raw specialist objects are large and the commander only has to coordinate,
    not restate. Sending the whole thing both costs tokens on every merge and
    buries the findings deep enough that the model stops reading them -- which
    showed up as a commander reporting "no findings received" while inventing
    conflicts that were not in the data.
    """
    if not isinstance(res, dict):
        return {"agent": agent_id, "findings": str(res)[:400]}
    keep = ("priority_actions", "conflicts", "bottlenecks", "shortfalls",
            "cascade_risks", "power_needs", "transport_needs", "outages",
            "single_points_of_failure", "closures", "recommended_routes",
            "shelter_plan", "hospital_status", "restoration_priority",
            "available", "allocations", "active_zones", "wind",
            "zones_to_evacuate_first", "vulnerable_population")

    def trim(v, depth=0):
        if isinstance(v, list):
            return [trim(x, depth + 1) for x in v[:4]]
        if isinstance(v, dict):
            return {k: trim(x, depth + 1) for k, x in list(v.items())[:8]}
        return (v[:220] if isinstance(v, str) else v)

    out = {k: trim(v) for k, v in res.items() if k in keep and v}
    out["confidence"] = res.get("confidence", "medium")
    return {"agent": agent_id, **out}


class Orchestrator:
    def __init__(self):
        self.hd = HotdataClient()
        self.tel = TelemetryStore(self.hd)
        self._warmed = False

    async def aclose(self):
        await self.hd.aclose()

    async def warm(self) -> float:
        ms = await self.hd.warm()
        self._warmed = True
        return ms

    # ---------------------------------------------------------------- databases
    async def _provision(self, run_id: str, agent_id: str, scen, overrides: dict | None) -> dict:
        """create -> load slice -> build bm25 index. One isolated DB per agent."""
        t0 = time.perf_counter()
        slice_ = scen.slice_for(agent_id, overrides)
        db = await self.hd.create_db(
            f"rg-{agent_id}-{run_id[:8]}",
            expires_at="2h",                       # crash-safety net only; we DELETE explicitly
            schemas=[{"name": "main", "tables": [{"name": t} for t in slice_]}],
            default_schema="main")
        dbid = db["id"]
        conn = db.get("default_connection_id", "")
        rows_total = 0
        for table, rows in slice_.items():
            r = await self.hd.load_rows(dbid, table, rows, mode="replace",
                                        idempotency_key=f"{run_id}-{agent_id}-{table}")
            rows_total += len(rows)
        # bm25 on the notes column gives the agent full-text search over its slice
        idx = None
        if conn:
            first = next(iter(slice_))
            notes_col = "notes" if any("notes" in r for r in slice_[first]) else None
            if notes_col:
                try:
                    await self.hd.build_index(conn, first, [notes_col],
                                              index_name=f"{first}_notes_bm25",
                                              schema="main", index_type="bm25")
                    idx = f"{first}.{notes_col}"
                except HotdataError:
                    idx = None
        BUS.emit(run_id, "db_created",
                 f"{AGENTS[agent_id].label}: isolated database ready ({rows_total} rows)",
                 agent_id=agent_id,
                 payload={"database_id": dbid, "tables": list(slice_), "rows": rows_total,
                          "bm25_index": idx, "provision_ms": _ms(t0), "state": "DATABASE_CREATED"})
        return {"agent": agent_id, "database_id": dbid, "connection_id": conn,
                "tables": list(slice_), "rows": rows_total, "provision_ms": _ms(t0)}

    async def _teardown(self, run_id: str, provisioned: list[dict], seq_base: dict[str, int]) -> None:
        """Snapshot Hotdata's own query telemetry BEFORE destroying each database."""
        async def one(p: dict):
            agent, dbid = p["agent"], p["database_id"]
            try:
                runs = await self.hd.query_runs(dbid)
                entries = [{
                    "database_id": dbid, "sql_text": q.get("sql_text", ""),
                    "sql_hash": q.get("sql_hash", ""),
                    "execution_time_ms": q.get("execution_time_ms") or 0,
                    "server_processing_ms": q.get("server_processing_ms") or 0,
                    "bytes_scanned": q.get("bytes_scanned") or 0,
                    "rows_scanned": q.get("rows_scanned") or 0,
                    "rows_returned": q.get("row_count") or 0,
                    "ok": 1 if q.get("status") == "succeeded" else 0,
                } for q in runs]
                self.tel.add_queries(run_id, agent, entries, seq_base.get(agent, 0))
                p["query_count"] = len(entries)
                p["query_ms_total"] = sum(e["execution_time_ms"] for e in entries)
            except Exception:
                p.setdefault("query_count", 0)
                p.setdefault("query_ms_total", 0)
            ok = await self.hd.delete_db(dbid)
            BUS.emit(run_id, "db_destroyed",
                     f"{AGENTS[agent].label}: database destroyed ({p.get('query_count', 0)} queries recorded)",
                     agent_id=agent, payload={"database_id": dbid, "deleted": ok,
                                              "query_count": p.get("query_count", 0)})
        await asyncio.gather(*(one(p) for p in provisioned), return_exceptions=True)

    # ---------------------------------------------------------------- pipeline
    async def _execute(self, run_id: str, mode: str, agent_ids: list[str],
                       db_ids: dict[str, str], brief: dict,
                       pipe: dict | None = None) -> dict:
        """Run a graph on the engine and translate its events into our stream."""
        pipe = pipe if pipe is not None else pipes.build(mode, db_ids, agent_ids=agent_ids)
        spans: dict[str, dict] = {a: {} for a in agent_ids}
        started_flag: dict[str, bool] = {}
        flow_events: list[dict] = []

        def mark_start(aid: str):
            if not started_flag.get(aid):
                started_flag[aid] = True
                spans[aid]["start"] = time.perf_counter()
                BUS.emit(run_id, "agent_started", f"{AGENTS[aid].label}: analyzing",
                         agent_id=aid, payload={"state": "ANALYZING"})

        def on_event(e: Any):
            if not isinstance(e, dict):
                return
            name, body = e.get("event"), e.get("body") or {}
            if name == "apaevt_flow":
                flow_events.append({"ts": time.perf_counter(), "body": body})
                node = str(body.get("pipeId") or body.get("component") or body.get("id") or "")
                for aid in agent_ids:
                    if node == aid or node.endswith(aid):
                        mark_start(aid)
                        spans[aid]["last"] = time.perf_counter()
                if COMMANDER_ID in node:
                    spans.setdefault(COMMANDER_ID, {}).setdefault("start", time.perf_counter())
            elif name == "output":
                line = str(body.get("text") or body.get("message") or "")[:200]
                if line.strip():
                    BUS.emit(run_id, "agent_update", line, payload={"source": "engine"})

        client = RocketRideClient(uri=config.ROCKETRIDE_URI, auth=config.ROCKETRIDE_AUTH,
                                  on_event=on_event)
        await client.connect()
        t_pipe = time.perf_counter()
        try:
            r = await client.use(pipeline=pipe, source=pipes.SOURCE_ID,
                                 threads=config.ENGINE_THREADS if mode == "parallel" else 1,
                                 pipelineTraceLevel="summary")
            token = r.get("token")
            if not token:
                raise RuntimeError(f"engine returned no token: {r}")
            await client.set_events(token, ["TASK", "SUMMARY", "FLOW", "OUTPUT", "SSE"])
            # In parallel mode every specialist reads the source, so one send fans out.
            timeout = config.AGENT_TIMEOUT_S * (len(agent_ids) + 1 if mode == "sequential" else 2)
            # MIME decides the lane: application/json lands on the `json` lane, which
            # no agent listens to. The question MIME routes to `questions`, which is
            # what agent_rocketride consumes.
            result = await asyncio.wait_for(
                client.send(token, json.dumps(brief), objinfo={"name": "incident_brief.json"},
                            mimetype="application/rocketride-question+json"),
                timeout=timeout)
            pipeline_ms = _ms(t_pipe)
            status = await client.get_task_status(token)
            sd = status if isinstance(status, dict) else getattr(status, "__dict__", {})
            await client.terminate(token)
        finally:
            await client.disconnect()

        per_agent_ms = {}
        for aid in agent_ids:
            s = spans.get(aid) or {}
            if s.get("start"):
                per_agent_ms[aid] = int(((s.get("last") or time.perf_counter()) - s["start"]) * 1000)
        return {"result": result or {}, "pipeline_ms": pipeline_ms, "status": sd,
                "per_agent_ms": per_agent_ms, "flow_event_count": len(flow_events),
                "pipe": pipe}

    # ---------------------------------------------------------------- run
    async def run(self, scenario_id: str, mode: str, *, run_id: str | None = None,
                  agent_ids: list[str] | None = None, overrides: dict | None = None,
                  parent_run_id: str = "", injected_event: str = "",
                  carry_results: dict | None = None) -> dict:
        scen = SCENARIOS[scenario_id]
        run_id = run_id or uuid.uuid4().hex
        ids = agent_ids or list(ORDER)
        started_at, t_run = _now(), time.perf_counter()
        RUNS[run_id] = {"run_id": run_id, "scenario": scenario_id, "execution_mode": mode,
                        "status": "running", "started_at": started_at, "agents": ids,
                        "parent_run_id": parent_run_id, "injected_event": injected_event}

        BUS.emit(run_id, "run_started",
                 f"{mode.upper()} run started: {len(ids)} specialist(s)",
                 payload={"scenario": scenario_id, "execution_mode": mode, "agents": ids,
                          "config_version": config.CONFIG_VERSION,
                          "parent_run_id": parent_run_id, "injected_event": injected_event})
        BUS.emit(run_id, "scenario_loaded", scen.SCENARIO_META["summary"],
                 payload={**scen.SCENARIO_META, "agent_tables":
                          {a: list(scen.slice_for(a, overrides)) for a in ids}})

        if not self._warmed:
            await self.warm()

        provisioned: list[dict] = []
        agent_results: dict[str, Any] = dict(carry_results or {})
        degraded: list[str] = []
        plan = None
        err = ""
        exec_out: dict = {}

        try:
            # ---- fan out: one isolated database per agent, created concurrently
            t_prov = time.perf_counter()
            provisioned = list(await asyncio.gather(
                *(self._provision(run_id, a, scen, overrides) for a in ids)))
            provision_ms = _ms(t_prov)
            db_ids = {p["agent"]: p["database_id"] for p in provisioned}
            BUS.emit(run_id, "metric_updated",
                     f"{len(provisioned)} isolated databases provisioned in {provision_ms} ms",
                     payload={"provision_ms": provision_ms,
                              "database_ids": db_ids, "distinct": len(set(db_ids.values()))})

            # ---- run the graph
            brief = {"scenario": scen.SCENARIO_META["name"],
                     "kind": scen.SCENARIO_META["kind"],
                     "declared_at": scen.SCENARIO_META["declared_at"],
                     "situation": scen.SCENARIO_META["summary"],
                     "disclaimer": scen.SCENARIO_META["disclaimer"],
                     "instruction": ("Query your own database, then report your findings as "
                                     "one JSON object in your specified shape.")}
            if carry_results:
                brief["known_findings"] = {k: v for k, v in carry_results.items() if k in ORDER}
            BUS.emit(run_id, "merge_started", "Specialists dispatched; commander awaiting fan-in",
                     payload={"mode": mode})

            if mode == "sequential":
                # A chained graph is NOT a valid baseline: an agent fed the previous
                # agent's `answers` lane receives nothing it treats as a query, so
                # downstream specialists no-op (measured: 4 of 5 ran zero queries).
                # The honest baseline is the SAME single-agent work, one at a time.
                result, per_agent, pipeline_ms = {}, {}, 0
                t_seq = time.perf_counter()
                for aid in ids:
                    t_a = time.perf_counter()
                    one = await self._execute(
                        run_id, "parallel", [aid], {aid: db_ids[aid]}, brief,
                        pipe=pipes.build("parallel", {aid: db_ids[aid]}, agent_ids=[aid]))
                    result.update(one.get("result") or {})
                    per_agent[aid] = _ms(t_a)
                    BUS.emit(run_id, "metric_updated",
                             f"{AGENTS[aid].label} finished in {per_agent[aid]} ms (serial)",
                             agent_id=aid, payload={"duration_ms": per_agent[aid],
                                                    "execution_mode": "sequential"})
                pipeline_ms = _ms(t_seq)
                exec_out = {"result": result, "pipeline_ms": pipeline_ms, "status": {},
                            "per_agent_ms": per_agent, "flow_event_count": 0, "pipe": None}
            else:
                exec_out = await self._execute(run_id, mode, ids, db_ids, brief)
            result = exec_out["result"]

            # ---- validate each specialist from its own sink
            for aid in ids:
                raw = result.get(aid)
                obj, why = validate_specialist(raw)
                if obj is None:
                    degraded.append(aid)
                    BUS.emit(run_id, "agent_completed", f"{AGENTS[aid].label}: DEGRADED ({why})",
                             agent_id=aid, payload={"state": "DEGRADED", "reason": why})
                else:
                    agent_results[aid] = obj.model_dump()
                    BUS.emit(run_id, "agent_completed",
                             f"{AGENTS[aid].label}: recommendation ready",
                             agent_id=aid,
                             payload={"state": "COMPLETE",
                                      "duration_ms": exec_out["per_agent_ms"].get(aid),
                                      "confidence": obj.confidence,
                                      "result": obj.model_dump()})

            # ---- the merge wave: a second RocketRide graph that receives all
            # five results in one payload (see pipes.build_merge for why).
            t_merge = time.perf_counter()
            merge_brief = {
                "scenario": scen.SCENARIO_META["name"],
                "situation": scen.SCENARIO_META["summary"],
                "disclaimer": scen.SCENARIO_META["disclaimer"],
                "specialist_findings": [_compact(a, r) for a, r in agent_results.items()],
                "missing_specialists": degraded,
                "instruction": ("Merge these specialist findings into ONE incident command "
                                "plan in your specified JSON shape. Resolve every conflict "
                                "where two domains need the same scarce resource."),
            }
            BUS.emit(run_id, "merge_started",
                     f"Incident Commander merging {len(agent_results)} specialist result(s)",
                     payload={"received": list(agent_results), "missing": degraded})
            merge_out = await self._execute(
                run_id, "merge", [], {}, merge_brief,
                pipe=pipes.build_merge(findings=merge_brief["specialist_findings"]))
            merge_ms = _ms(t_merge)
            result = {**result, **(merge_out.get("result") or {})}
            exec_out["merge_ms"] = merge_ms
            exec_out["status"] = merge_out.get("status") or exec_out.get("status")

            plan_obj, why = validate_plan(result.get(pipes.PLAN_LANE))
            if plan_obj is None:
                err = f"commander output unusable: {why}"
                BUS.emit(run_id, "error", err, payload={"stage": "merge"})
            else:
                plan_obj.degraded_agents = degraded
                plan_obj.generated_at = _now()
                plan = plan_obj.model_dump()
                for c in plan.get("resource_conflicts", []):
                    BUS.emit(run_id, "conflict_detected",
                             f"Conflict on {c.get('resource')}: {c.get('resolution')}",
                             payload=c)
                BUS.emit(run_id, "plan_updated", plan.get("executive_summary", "Plan updated"),
                         payload={"plan": plan})
                BUS.emit(run_id, "merge_completed",
                         f"Incident Command Plan ready ({plan.get('incident_status')})",
                         payload={"incident_status": plan.get("incident_status"),
                                  "conflicts": len(plan.get("resource_conflicts", [])),
                                  "degraded_agents": degraded})
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:400]
            BUS.emit(run_id, "error", err, payload={"stage": "run"})
        finally:
            seq_base = {a: 0 for a in ids}
            if provisioned:
                await self._teardown(run_id, provisioned, seq_base)

        duration_ms = _ms(t_run)
        status_d = exec_out.get("status") or {}
        custom = ((status_d.get("tokens") or {}).get("custom")) or {}
        tok_in = int(custom.get("llm_input_tokens") or 0)
        tok_out = int(custom.get("llm_output_tokens") or 0)
        model_calls = int(custom.get("llm_calls") or 0)
        ok_agents = [a for a in ids if a in agent_results and a not in degraded]

        # ---- telemetry: buffered here, flushed once, by this single writer
        for p in provisioned:
            aid = p["agent"]
            self.tel.add("agent_runs", {
                "run_id": run_id, "agent": aid, "execution_mode": mode,
                "config_version": config.CONFIG_VERSION, "started_at": started_at,
                "ended_at": _now(),
                "duration_ms": exec_out.get("per_agent_ms", {}).get(aid, 0),
                "model": config.SPECIALIST_PROFILE, "model_calls": 0, "waves": config.MAX_WAVES,
                "input_tokens": 0, "output_tokens": 0, "est_cost_usd": 0.0,
                "hotdata_db_id": p["database_id"], "query_count": p.get("query_count", 0),
                "query_ms_total": p.get("query_ms_total", 0), "retries": 0,
                "status": "degraded" if aid in degraded else ("ok" if aid in agent_results else "failed"),
                "note": (f"{AGENTS[aid].label} over tables {','.join(p['tables'])}; "
                         f"{p.get('query_count', 0)} queries; "
                         f"{'degraded' if aid in degraded else 'nominal'}"),
            })
        status = "complete" if plan else ("degraded" if agent_results else "failed")
        self.tel.add("runs", {
            "run_id": run_id, "parent_run_id": parent_run_id, "scenario": scenario_id,
            "execution_mode": mode, "config_version": config.CONFIG_VERSION,
            "started_at": started_at, "ended_at": _now(), "duration_ms": duration_ms,
            "merge_duration_ms": exec_out.get("merge_ms", 0), "model_calls": model_calls,
            "input_tokens": tok_in, "output_tokens": tok_out,
            "est_cost_usd": config.estimate_cost(config.SPECIALIST_PROFILE, tok_in, tok_out),
            "agents_ok": len(ok_agents), "agents_failed": len(degraded),
            "injected_event": injected_event, "status": status,
            "notes": err[:200] or f"{mode} run over {len(ids)} agents",
        })
        flushed = await self.tel.flush()

        rec = RUNS[run_id]
        rec.update({"status": status, "ended_at": _now(), "duration_ms": duration_ms,
                    "pipeline_ms": exec_out.get("pipeline_ms"),
                    "merge_ms": exec_out.get("merge_ms"),
                    "per_agent_ms": exec_out.get("per_agent_ms", {}),
                    "agent_results": agent_results, "degraded_agents": degraded,
                    "plan": plan, "error": err,
                    "databases": {p["agent"]: p["database_id"] for p in provisioned},
                    "query_counts": {p["agent"]: p.get("query_count", 0) for p in provisioned},
                    "tokens": {"input": tok_in, "output": tok_out},
                    "telemetry_flush": flushed,
                    "flow_events": exec_out.get("flow_event_count", 0)})
        crit = max(rec["per_agent_ms"].items(), key=lambda kv: kv[1], default=(None, 0))
        rec["critical_path_agent"] = crit[0]
        BUS.emit(run_id, "run_completed",
                 f"{mode.upper()} run {status} in {duration_ms} ms",
                 payload={"status": status, "duration_ms": duration_ms,
                          "per_agent_ms": rec["per_agent_ms"],
                          "critical_path_agent": crit[0],
                          "degraded_agents": degraded, "error": err,
                          "telemetry_flush": flushed})
        return rec

    # ---------------------------------------------------------------- injection
    async def inject(self, run_id: str, kind: str, payload: dict | None = None) -> dict:
        """Rerun ONLY the domains the new condition invalidates, then re-merge."""
        base = RUNS.get(run_id)
        if not base:
            raise KeyError(run_id)
        if kind not in INJECTION_IMPACT:
            raise ValueError(f"unknown injection {kind!r}")
        affected = INJECTION_IMPACT[kind]
        overrides = INJECTION_OVERRIDES.get(kind, {})
        BUS.emit(run_id, "incident_injected",
                 f"{kind.replace('_', ' ').upper()} -- reruning {', '.join(affected)}",
                 payload={"kind": kind, "affected_agents": affected,
                          "unchanged_agents": [a for a in base.get("agents", ORDER) if a not in affected],
                          "detail": payload or {}, "overrides": overrides})
        carry = {k: v for k, v in (base.get("agent_results") or {}).items() if k not in affected}
        return await self.run(base["scenario"], base["execution_mode"],
                              agent_ids=affected, overrides=overrides,
                              parent_run_id=run_id, injected_event=kind,
                              carry_results=carry)


# Deterministic scenario mutations per injection: what actually changed on the ground.
INJECTION_OVERRIDES: dict[str, dict] = {
    "road_blocked": {"routes": [
        {"route_id": "RT-PCH-S", "status": "closed", "current_flow_vph": 0,
         "congestion": "none", "notes": "CLOSED - structure fire jumped PCH at Temescal."}]},
    "hospital_power_loss": {"facilities": [
        {"facility_id": "HOSP-1", "power_source": "failed", "backup_hours": 0,
         "er_status": "diversion", "notes": "Utility feed AND backup generator down. Surgical load at risk."}]},
    "shelter_full": {"facilities": [
        {"facility_id": "SHLT-1", "current_occupancy": 800, "available": 0,
         "notes": "AT CAPACITY - no further intake."}]},
    "wind_shift": {"weather": [
        {"obs_id": "WX-1", "wind_from_deg": 212, "gust_mph": 68,
         "trend": "ABRUPT REVERSAL - now onshore", "notes": "Wind reversal pushes fire back over burned flank toward ZONE-D."}]},
    "infrastructure_failure": {"utilities": [
        {"asset_id": "COM-1", "status": "failed", "restore_eta_hours": 0,
         "notes": "FAILED - generator fuel exhausted. Wireless alerts dark in ZONE-B and ZONE-C."}]},
    "new_hazard_zone": {"hazards": [
        {"hazard_id": "FZ-3", "acres": 140, "intensity": "extreme", "spread_rate_mph": 2.1,
         "structures_at_risk": 260, "notes": "ESCALATED - spot fire established its own run into Rustic Canyon."}]},
}
