# ResponseGrid

**Parallel intelligence for emergency response.**

> Emergencies don't happen one problem at a time. ResponseGrid doesn't solve them one at a time.

ResponseGrid is an AI incident-command system. When an emergency is declared it launches five
specialist agents **simultaneously** — hazard, evacuation, medical, infrastructure, logistics.
Each agent gets its **own isolated Hotdata database** loaded with only the slice of operational
data its domain needs, queries it independently, and returns structured findings. An Incident
Commander then merges those findings into a single coordinated **Incident Command Plan**,
resolving the conflicts that arise when five domains compete for the same scarce resources.

Built for the Devnovate **Data & AI Hackathon — Parallel Agents** track.
Orchestration: **RocketRide**. Data layer: **Hotdata**.

---

## Architecture

```
POST /api/runs
      │
      ├── slice the scenario per agent (deterministic code, no LLM)
      │
      ├── asyncio.gather ×5  ──▶  Hotdata: create DB → load slice → build bm25 index
      │                            (5 distinct dbid…, one per agent)
      ▼
  RocketRide engine  ── use(pipeline=…, threads=16, pipelineTraceLevel="summary")
      │
      ├─────────── 5 independent graph branches, run concurrently ───────────┐
   hazard     evacuation     medical     infrastructure     logistics
   (agent_rocketride ×5, each bound to: llm_anthropic + memory_internal + its own db_hotdata)
      └─────────── fan-in: 5 × {lane:"answers"} ────────────────────────────┘
      ▼
  incident_commander (agent_rocketride, Sonnet) ──▶ response sinks
      ▼
  validate (pydantic) → snapshot query-runs → DELETE ×5 databases → flush telemetry
      ▼
  responsegrid_telemetry  (permanent Hotdata DB, accumulates across every run)
```

### Why the databases are created by us, not by the node

`db_hotdata` can provision its own ephemeral database per run. We don't let it, because then we
could not emit `db_created` with a real database id, could not preload each agent's slice, and
could not build indexes. Instead the backend creates each task database over the REST API, loads
the slice, builds a bm25 index, passes the id in as `hotdata.database_id` (attached mode — the
node never deletes an attached database), and deletes it explicitly at teardown. The
**create → load → query → destroy** lifecycle is therefore explicit and observable in the event
stream, which is the point.

---

## Quick start

```bash
# 0. deps (Python 3.10+ required by the RocketRide SDK)
uv venv --python 3.13 .venv
VIRTUAL_ENV=.venv uv pip install rocketride httpx fastapi "uvicorn[standard]" pydantic python-dotenv

# 1. secrets
cp .env.example .env      # then fill in the keys (see below)

# 2. the RocketRide engine (local, no API key needed)
./scripts/start_engine.sh

# 3. the permanent telemetry database (idempotent; safe to re-run)
./.venv/bin/python scripts/bootstrap_telemetry.py

# 4. the API
./scripts/start_api.sh
# -> http://127.0.0.1:8000  (docs at /docs)

# 5. prove it
curl -s localhost:8000/api/health | python3 -m json.tool
curl -sX POST localhost:8000/api/runs -H 'content-type: application/json' \
     -d '{"scenario":"palisades_wildfire","execution_mode":"parallel"}'
```

### Environment

| Variable | Required | Notes |
|---|---|---|
| `HOTDATA_API_KEY` | yes | From hotdata.dev. |
| `HOTDATA_WORKSPACE_ID` | yes | `work…`; sent as `X-Workspace-Id` on every call. |
| `ANTHROPIC_API_KEY` | **yes** | Must start with `sk-ant` — the `llm_anthropic` node validates the format at pipeline startup and refuses anything else. |
| `ROCKETRIDE_URI` | yes | `ws://localhost:5565` for the local engine, `https://api.rocketride.ai` for Cloud. |
| `ROCKETRIDE_AUTH` | Cloud only | Not needed for a local engine. |
| `TELEMETRY_DB_ID` | auto | Written by `bootstrap_telemetry.py`. |
| `CONFIG_VERSION` | no | Bump it before a tuning change so telemetry can compare before/after. |

`.env` is gitignored. No key is ever committed.

---

## Measured results, and what they are worth

Numbers from real runs on 2026-09-11, local engine, Claude Haiku 4.5 specialists.

| | sequential | parallel |
|---|---|---|
| wall clock | **218,952 ms** | **171,783 ms** |
| Hotdata queries | 42 | 33 |
| specialists completing | 5/5 | 5/5 |

That is a **1.27x** speedup, n=1 in each mode, on one laptop sharing CPU with the
engine. Treat it as directional, not a benchmark. The best parallel run observed was
66,203 ms; parallel run durations varied from 66s to 184s depending on machine load,
so a defensible figure needs several runs per mode on a quiet machine.

Two measurement traps we hit, recorded here because both produced *flattering* wrong
answers at first:

1. **The chained `.pipe` is not a valid sequential baseline.** An agent fed the previous
   agent's `answers` lane does not treat that data as its query, so downstream
   specialists no-op — measured: 4 of 5 agents ran **zero** queries, and "sequential"
   came out 2.5x *faster* than parallel because it was barely working. The real baseline
   runs the same single-agent graph once per specialist, serially. `responsegrid_sequential.pipe`
   is kept for reference and is explicitly not what the benchmark uses.
2. **Per-agent durations are not trustworthy.** Engine flow events mark node
   initialisation, not the start of an agent's work, so derived per-agent spans come out
   near-identical within a run. `/api/telemetry/bottleneck` therefore ranks on query
   volume, zero-query runs, retries and failures — all measured directly — and says so
   in its response.

**Token and cost telemetry is unavailable**, not estimated. The local engine did not
populate `TASK_STATUS.tokens.custom` with `llm_input_tokens`/`llm_output_tokens` on
these runs, so those columns are 0 and `/api/telemetry/summary` reports
`token_accounting: "unavailable"` rather than inventing a figure.

### What telemetry actually changed

Across 10 agent-runs, `logistics` had the fewest queries (2.6 avg), the most
zero-query runs (6) and the most failures (2) — while carrying the widest slice, 4
tables. It was spending its wave budget discovering tables instead of answering. We
narrowed it to the 2 tables it reasons over and gave it an explicit "query resources
first" hint (`CONFIG_VERSION` v2). Compare versions live at
`/api/telemetry/config-compare`.

## Verification

```bash
./.venv/bin/python scripts/smoke_hotdata.py      # create → load → query → append → query-runs → delete
./.venv/bin/python scripts/smoke_rocketride.py   # connect → use → send → status → terminate
./.venv/bin/python scripts/bootstrap_telemetry.py  # re-run: prints created=False, destroys nothing
```

The parallelism proof is in the event stream, not in a claim: five `db_created` events carrying
five **distinct** `dbid…` values, five `agent_started` events landing within about a second of
each other, and five `db_destroyed` events at teardown.

---

## Data honesty

Every row in `backend/scenarios/palisades.py` is **simulated** and tagged `data_source:
"simulated"`. The scenario is *inspired by* the geography of Pacific Palisades, CA; the
operational figures — unit positions, hospital capacities, road closures — are invented for the
exercise and are not historical fact.

Measured numbers are measured. Durations come from wall-clock timing around real runs, query
latencies from Hotdata's own `execution_time_ms`, and token counts from the engine's
`llm_input_tokens` / `llm_output_tokens` counters. No speedup, cost, or latency figure in this
repo is hard-coded.

---

## Layout

```
backend/
  main.py          FastAPI app, 21 endpoints, SSE stream
  orchestrator.py  run lifecycle, DB lifecycle, injection reruns
  pipes.py         builds the parallel + sequential .pipe graphs
  agents.py        the 5 specialists, the commander, the injection impact map
  hotdata.py       Hotdata client (httpx, Retry-After aware)
  telemetry.py     buffered single-writer telemetry + the live queries
  schemas.py       pydantic validation, tolerant JSON extraction
  events.py        event bus → SSE with replay
  scenarios/palisades.py
pipes/             responsegrid_parallel.pipe, responsegrid_sequential.pipe  ← submitted
scripts/           start_engine.sh, start_api.sh, bootstrap_telemetry.py, smoke_*.py
CODEX_HANDOFF.md   the frontend contract
DEMO_SCRIPT.md     the 3-minute demo
```
