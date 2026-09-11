# ResponseGrid — Frontend Handoff

Everything you need to build the UI. You should not need to read any backend source.

- **Base URL:** `http://127.0.0.1:8000`
- **Start the backend:** `./scripts/start_engine.sh && ./scripts/start_api.sh`
- **Interactive API docs:** `http://127.0.0.1:8000/docs`
- CORS is wide open, so a Vite/Next dev server on any port can call it directly.

Check `GET /api/health` first. If it returns `"blocker"`, the backend is up but agents cannot run
— surface that string in the UI rather than showing an empty dashboard.

---

## The visual target

A **dark emergency command center**. Not a chat UI, and not five chat panes side by side — one
intelligent system composed of specialized parallel capabilities. Someone watching for ten
seconds should grasp: a crisis happened → five specialists launched *at the same time* → each had
its own data → they solved different pieces → the results merged → one coordinated plan came out
→ it was faster than doing it one at a time → and when reality changed, it adapted.

Layout:

- **Center:** the incident — scenario name, status, the live Incident Command Plan as it arrives.
- **Around/beside it:** five agent cards that **light up simultaneously**. This is the money
  shot; if they appear to start one after another the whole story collapses. Animate the state
  transitions and show each card's live query count and elapsed time.
- **Bottom/side:** the incident timeline (the event stream, newest first).
- **Prominent:** a large **parallel vs sequential** metric, and an obvious **INJECT EVENT**
  control.
- **Panel:** telemetry — bottleneck, cost, cross-run comparison.

Agent card states, in order:

`IDLE → DATABASE_CREATED → ANALYZING → QUERYING → RECOMMENDATION_READY → COMPLETE`

plus `DEGRADED` (that agent failed; the plan still ships without it — show it amber, not as a
crash).

The five agents, in display order — `GET /api/agents` returns this:

| id | label | domain |
|---|---|---|
| `hazard` | FIRE / HAZARD | hazard intelligence |
| `evacuation` | EVACUATION + TRAFFIC | evacuation and traffic |
| `medical` | MEDICAL + SHELTER | medical and sheltering |
| `infrastructure` | INFRASTRUCTURE + UTILITIES | infrastructure and utilities |
| `logistics` | LOGISTICS + RESOURCES | logistics and resources |

---

## Core flow

```js
// 1. start a run
const { run_id, events_url } = await fetch('http://127.0.0.1:8000/api/runs', {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ scenario: 'palisades_wildfire', execution_mode: 'parallel' }),
}).then(r => r.json());

// 2. stream it
const es = new EventSource(`http://127.0.0.1:8000${events_url}`);
es.onmessage = (m) => update(JSON.parse(m.data));   // every event also arrives here
es.addEventListener('db_created',   e => markDbReady(JSON.parse(e.data)));
es.addEventListener('agent_started', e => setState(JSON.parse(e.data), 'ANALYZING'));
es.addEventListener('plan_updated',  e => renderPlan(JSON.parse(e.data).payload.plan));
es.addEventListener('run_completed', e => { finish(JSON.parse(e.data)); es.close(); });

// 3. inject a disruption mid-demo
await fetch(`http://127.0.0.1:8000/api/runs/${run_id}/inject`, {
  method: 'POST', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ type: 'road_blocked' }),
});
```

`POST /api/runs` returns immediately with `status: "queued"`; the run happens in the background
and the SSE stream is the source of truth. Each event type is dispatched as its **own** named SSE
event *and* through `onmessage`, so use whichever is convenient.

**Late connections are fine.** The stream replays every event already emitted for that run
before going live, so you can attach whenever and still draw the full history. A `: keepalive`
comment arrives every 15s.

---

## SSE event envelope

Every event, without exception:

```json
{
  "ts": 1789156445.018,
  "run_id": "9f2c…",
  "seq": 7,
  "event_type": "db_created",
  "agent_id": "hazard",
  "message": "FIRE / HAZARD: isolated database ready (10 rows)",
  "payload": { "...": "type-specific" }
}
```

`agent_id` is `null` for run-level events. `seq` is monotonic per run — use it to order, not `ts`.
`message` is written to be displayed as-is in the timeline.

### Event types and their payloads

| `event_type` | when | key payload fields |
|---|---|---|
| `run_started` | run begins | `scenario`, `execution_mode`, `agents[]`, `config_version`, `parent_run_id`, `injected_event` |
| `scenario_loaded` | scenario resolved | `id`, `name`, `kind`, `summary`, `disclaimer`, `agent_tables{}` |
| `db_created` | an agent's DB is ready | `database_id`, `tables[]`, `rows`, `bm25_index`, `provision_ms`, `state:"DATABASE_CREATED"` |
| `agent_started` | agent begins work | `state:"ANALYZING"` |
| `agent_query` | agent queried its DB | `sql`, `execution_time_ms`, `rows` |
| `agent_update` | progress line | `source` |
| `agent_completed` | agent finished | `state:"COMPLETE"\|"DEGRADED"`, `duration_ms`, `confidence`, `result{}`, `reason` |
| `db_destroyed` | agent's DB deleted | `database_id`, `deleted`, `query_count` |
| `merge_started` | specialists dispatched | `mode` |
| `conflict_detected` | commander found a conflict | `resource`, `contenders`, `resolution`, `rationale` |
| `plan_updated` | plan available/revised | `plan{}` (full Incident Command Plan) |
| `merge_completed` | merge done | `incident_status`, `conflicts`, `degraded_agents[]` |
| `metric_updated` | a measurement landed | `provision_ms`, `database_ids{}`, `distinct` |
| `run_completed` | terminal | `status`, `duration_ms`, `per_agent_ms{}`, `critical_path_agent`, `degraded_agents[]`, `telemetry_flush{}` |
| `incident_injected` | disruption injected | `kind`, `affected_agents[]`, `unchanged_agents[]`, `overrides{}` |
| `error` | something failed | `stage` |

> **The parallelism proof, for the UI:** the five `db_created` events carry five **distinct**
> `database_id` values, and the five `agent_started` events land within about a second of one
> another. Showing `payload.database_id` on each card makes the isolation visible and concrete.

---

## Incident Command Plan

Delivered in `plan_updated.payload.plan`, and on the finished run at `GET /api/runs/{id}` → `.plan`.

```json
{
  "incident_status": "critical",
  "executive_summary": "Wind-driven fire threatens 2,400 structures…",
  "immediate_actions": [
    { "rank": 1, "action": "Commit E-14 to Palisades Dr corridor", "owner": "logistics", "why": "Only egress for ZONE-A" }
  ],
  "evacuation_actions": ["Shift ZONE-C to Chautauqua; PCH at 91% capacity"],
  "medical_actions": ["Pre-stage AMB-7 for the CARE-1 lift"],
  "infrastructure_actions": ["Assign GEN-3 to HOSP-1 over the signal cluster"],
  "logistics_actions": ["Hold DZ-2 for the FZ-3 spot"],
  "resource_conflicts": [
    { "resource": "GEN-3", "contenders": "HOSP-1 vs PWR-2",
      "resolution": "HOSP-1", "rationale": "Surgical load is life-safety; signals degrade to stop-controlled" }
  ],
  "critical_dependencies": [{ "depends_on": "PWR-1", "blocks": "WTR-1 hydrant pressure" }],
  "unresolved_risks": ["AIR-1 grounded while gusts exceed 55 mph"],
  "agent_consensus": "minor_conflicts",
  "degraded_agents": [],
  "generated_at": "2026-09-11T21:15:03.412+00:00"
}
```

`incident_status` ∈ `critical | severe | elevated | stable`.
`agent_consensus` ∈ `aligned | minor_conflicts | major_conflicts`.
All list fields can be empty; `degraded_agents` naming an agent means that agent's findings are
absent, and the plan was built without them. Model output is validated but permissive — treat
every field as possibly missing and render defensively.

---

## Injection (the live disruption)

`GET /api/injections` returns the valid types and exactly which agents each one reruns:

| type | reruns |
|---|---|
| `road_blocked` | evacuation, logistics |
| `hospital_power_loss` | medical, infrastructure |
| `shelter_full` | medical, evacuation |
| `wind_shift` | hazard, evacuation |
| `infrastructure_failure` | infrastructure, logistics |
| `new_hazard_zone` | hazard, evacuation, medical |

`POST /api/runs/{run_id}/inject` → `{ ok, parent_run_id, type, affected_agents, unchanged_agents }`.

Scope is decided deterministically in code, not by a model. **Only the affected agents rerun**
— with fresh databases holding the mutated data — while the unaffected specialists' existing
findings are carried forward, and the commander re-merges. The `incident_injected` event fires on
the **parent** run's stream; the rerun is a **new run** with `parent_run_id` set, so subscribe to
the new `run_id` from `GET /api/runs` (newest, matching `parent_run_id`) to stream it. For the UI,
dim the unchanged cards and re-animate only the affected ones — that contrast is the whole point.

---

## Benchmark

`GET /api/benchmark`

```json
{
  "measured_speedup": 3.4,
  "by_mode_all_runs": {
    "parallel":   { "execution_mode": "parallel",   "runs": 6, "avg_ms": 18421, "best_ms": 16980, "avg_cost_usd": 0.0391 },
    "sequential": { "execution_mode": "sequential", "runs": 2, "avg_ms": 62310, "best_ms": 60104, "avg_cost_usd": 0.0402 }
  },
  "latest_in_process": {
    "parallel": { "last_duration_ms": 17233, "per_agent_ms": { "hazard": 9120, "evacuation": 14004 }, "critical_path_agent": "evacuation" }
  },
  "totals": { "total_runs": 8, "model_calls": 61, "input_tokens": 148233, "output_tokens": 21044, "total_cost_usd": 0.3108 }
}
```

`measured_speedup` is `mean sequential duration / mean parallel duration` over completed runs, and
is `null` until at least one run of **each** mode has completed. Numbers above are shape
illustrations — the real values come from measured runs.

Display it big. To populate it, run once in each mode before demoing.

---

## Telemetry

All of these are live SQL against the permanent `responsegrid_telemetry` Hotdata database, which
accumulates across every run.

| endpoint | returns |
|---|---|
| `GET /api/telemetry/summary` | per-mode run counts, mean/best duration, mean cost, `measured_speedup`, day totals |
| `GET /api/telemetry/agents` | per agent × mode: runs, mean/worst ms, mean queries, mean cost, retries, failures |
| `GET /api/telemetry/bottleneck` | which agent is the critical path and **how often**, across all parallel runs |
| `GET /api/telemetry/queries` | per agent: query count, mean, **p50/p95** latency, bytes scanned |
| `GET /api/telemetry/runs?limit=25` | recent runs, newest first |
| `GET /api/telemetry/config-compare` | mean duration and cost grouped by `config_version` — the before/after of a tuning change |
| `GET /api/telemetry/search?q=degraded` | full-text (bm25) over agent notes |
| `POST /api/telemetry/flush` | force a flush (normally automatic at run end) |

Rows are written once per run by a single batched writer, so a run's telemetry is queryable the
moment `run_completed` fires.

---

## Other endpoints

| endpoint | purpose |
|---|---|
| `GET /api/health` | Hotdata + RocketRide reachability, `missing_env[]`, `blocker` |
| `GET /api/scenarios` | scenarios with table row counts and the agent roster |
| `GET /api/agents` | agent order, labels, domains, tables, the state list |
| `GET /api/event-types` | every event type and agent state (handy for exhaustive switches) |
| `GET /api/runs` | all runs this process has seen (no heavy fields) |
| `GET /api/runs/{id}` | full run record: plan, per-agent results, timings, database ids, query counts |
| `GET /api/runs/{id}/history` | the event log for a run as an array (alternative to SSE) |
| `GET /api/pipes/parallel` \| `/sequential` | the raw `.pipe` JSON — nice as a "show the graph" view |

---

## Errors

- Bad scenario or `execution_mode` → `400` with a message.
- Unknown `run_id` → `404`.
- Unknown injection type → `400` with `valid[]` listing the accepted types.
- Orchestrator not ready → `503`.
- A **failed agent does not fail the run**: it lands in `degraded_agents` and the plan is built
  from the rest. Run `status` is `complete` (plan produced), `degraded` (some findings, no plan),
  or `failed`.
- If the whole run breaks you get an `error` event with a `stage`, then `run_completed` with
  `status: "failed"` — always terminal, so the UI can always stop spinning.
