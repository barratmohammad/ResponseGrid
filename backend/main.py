"""ResponseGrid API. Everything the frontend needs; see CODEX_HANDOFF.md."""
from __future__ import annotations
import asyncio, json, time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import config, pipes
from agents import AGENTS, INJECTION_IMPACT, ORDER
from events import AGENT_STATES, BUS, EVENT_TYPES, sse
from orchestrator import RUNS, SCENARIOS, Orchestrator

ORCH: Orchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ORCH
    ORCH = Orchestrator()
    try:
        await ORCH.warm()          # absorb the Hotdata cold start before any demo
    except Exception as e:
        print("warn: hotdata warm failed:", e)
    yield
    await ORCH.aclose()


app = FastAPI(title="ResponseGrid", version="1.0", lifespan=lifespan,
              description="Parallel intelligence for emergency response.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)


class RunRequest(BaseModel):
    scenario: str = "palisades_wildfire"
    execution_mode: str = "parallel"          # parallel | sequential


class InjectRequest(BaseModel):
    type: str
    payload: dict | None = None


def orch() -> Orchestrator:
    if ORCH is None:
        raise HTTPException(503, "orchestrator not ready")
    return ORCH


# ------------------------------------------------------------------ meta
@app.get("/api/health")
async def health():
    o = orch()
    out = {"ok": True, "missing_env": config.missing(),
           "engine_uri": config.ROCKETRIDE_URI,
           "config_version": config.CONFIG_VERSION,
           "telemetry_db": config.TELEMETRY_DB_ID or None}
    t0 = time.perf_counter()
    try:
        await o.hd.warm()
        out["hotdata"] = {"ok": True, "latency_ms": int((time.perf_counter() - t0) * 1000)}
    except Exception as e:
        out["hotdata"] = {"ok": False, "error": str(e)[:200]}
        out["ok"] = False
    try:
        from rocketride import RocketRideClient
        c = RocketRideClient(uri=config.ROCKETRIDE_URI, auth=config.ROCKETRIDE_AUTH)
        await asyncio.wait_for(c.connect(), timeout=15)
        out["rocketride"] = {"ok": c.is_connected(), "uri": config.ROCKETRIDE_URI}
        await c.disconnect()
    except Exception as e:
        out["rocketride"] = {"ok": False, "error": str(e)[:200]}
        out["ok"] = False
    if not config.ANTHROPIC_API_KEY:
        out["ok"] = False
        out["blocker"] = "ANTHROPIC_API_KEY is not set; specialist agents cannot run."
    return out


@app.get("/api/scenarios")
async def scenarios():
    return {"scenarios": [{**m.SCENARIO_META,
                           "tables": {k: len(v) for k, v in m.TABLES.items()},
                           "agents": [{"id": a, "label": AGENTS[a].label,
                                       "domain": AGENTS[a].domain,
                                       "tables": list(AGENTS[a].tables)} for a in ORDER]}
                          for m in SCENARIOS.values()]}


@app.get("/api/agents")
async def agents_list():
    return {"order": ORDER, "states": AGENT_STATES,
            "agents": [{"id": a, "label": AGENTS[a].label, "domain": AGENTS[a].domain,
                        "tables": list(AGENTS[a].tables)} for a in ORDER]}


@app.get("/api/injections")
async def injections():
    return {"types": [{"type": k, "affected_agents": v} for k, v in INJECTION_IMPACT.items()]}


@app.get("/api/event-types")
async def event_types():
    return {"event_types": EVENT_TYPES, "agent_states": AGENT_STATES}


@app.get("/api/pipes/{name}")
async def get_pipe(name: str):
    p = pipes.PIPE_DIR / (name if name.endswith(".pipe") else f"responsegrid_{name}.pipe")
    if not p.exists():
        raise HTTPException(404, f"no such pipe: {p.name}")
    return json.loads(p.read_text())


# ------------------------------------------------------------------ runs
@app.post("/api/runs")
async def create_run(req: RunRequest):
    if req.scenario not in SCENARIOS:
        raise HTTPException(400, f"unknown scenario {req.scenario!r}")
    if req.execution_mode not in ("parallel", "sequential"):
        raise HTTPException(400, "execution_mode must be 'parallel' or 'sequential'")
    import uuid
    run_id = uuid.uuid4().hex
    RUNS[run_id] = {"run_id": run_id, "scenario": req.scenario,
                    "execution_mode": req.execution_mode, "status": "queued"}
    asyncio.create_task(orch().run(req.scenario, req.execution_mode, run_id=run_id))
    return {"run_id": run_id, "status": "queued",
            "events_url": f"/api/runs/{run_id}/events",
            "scenario": req.scenario, "execution_mode": req.execution_mode}


@app.get("/api/runs")
async def list_runs():
    return {"runs": [{k: v for k, v in r.items()
                      if k not in ("agent_results", "plan")} for r in RUNS.values()]}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    r = RUNS.get(run_id)
    if not r:
        raise HTTPException(404, "unknown run")
    return r


@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, request: Request):
    q = BUS.subscribe(run_id)

    async def gen():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                    yield sse(ev)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"      # keep proxies from closing the stream
        finally:
            BUS.unsubscribe(run_id, q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                                      "Connection": "keep-alive"})


@app.get("/api/runs/{run_id}/history")
async def run_history(run_id: str):
    return {"run_id": run_id, "events": BUS.history(run_id)}


@app.post("/api/runs/{run_id}/inject")
async def inject(run_id: str, req: InjectRequest):
    if run_id not in RUNS:
        raise HTTPException(404, "unknown run")
    if req.type not in INJECTION_IMPACT:
        raise HTTPException(400, {"error": f"unknown injection {req.type!r}",
                                  "valid": list(INJECTION_IMPACT)})
    affected = INJECTION_IMPACT[req.type]
    asyncio.create_task(orch().inject(run_id, req.type, req.payload))
    return {"ok": True, "parent_run_id": run_id, "type": req.type,
            "affected_agents": affected,
            "unchanged_agents": [a for a in ORDER if a not in affected],
            "note": "watch the parent run's event stream for incident_injected, then the child run"}


# ------------------------------------------------------------------ benchmark
@app.get("/api/benchmark")
async def benchmark():
    """Measured only. Nothing here is computed from anything but observed runs."""
    o = orch()
    summary = await o.tel.summary()
    by = {r["execution_mode"]: r for r in summary.get("by_mode", [])}
    local = {}
    for mode in ("parallel", "sequential"):
        rs = [r for r in RUNS.values()
              if r.get("execution_mode") == mode and r.get("status") == "complete"
              and r.get("duration_ms")]
        if rs:
            last = rs[-1]
            local[mode] = {"last_duration_ms": last["duration_ms"],
                           "per_agent_ms": last.get("per_agent_ms", {}),
                           "critical_path_agent": last.get("critical_path_agent")}
    return {"measured_speedup": summary.get("measured_speedup"),
            "by_mode_all_runs": by, "latest_in_process": local,
            "totals": summary.get("totals", {}),
            "note": "speedup = mean sequential duration / mean parallel duration, over completed runs"}


# ------------------------------------------------------------------ telemetry
@app.get("/api/telemetry/summary")
async def tel_summary():
    return await orch().tel.summary()


@app.get("/api/telemetry/agents")
async def tel_agents():
    return {"agents": await orch().tel.agents()}


@app.get("/api/telemetry/runs")
async def tel_runs(limit: int = 25):
    return {"runs": await orch().tel.recent_runs(limit)}


@app.get("/api/telemetry/queries")
async def tel_queries():
    return {"query_profile": await orch().tel.query_profile()}


@app.get("/api/telemetry/bottleneck")
async def tel_bottleneck():
    return {"bottleneck": await orch().tel.bottleneck()}


@app.get("/api/telemetry/config-compare")
async def tel_config():
    return {"by_config_version": await orch().tel.config_compare()}


@app.get("/api/telemetry/search")
async def tel_search(q: str, limit: int = 10):
    """Full-text (bm25) over agent notes -- the search half of the data layer."""
    return {"query": q, "matches": await orch().tel.search_notes(q, limit)}


@app.post("/api/telemetry/flush")
async def tel_flush():
    return await orch().tel.flush()
