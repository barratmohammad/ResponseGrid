# ResponseGrid — 3-Minute Demo

**Before you walk up:** `./scripts/start_engine.sh`, `./scripts/start_api.sh`, then
`curl -s localhost:8000/api/health` (must be `ok: true`). Run **one parallel and one sequential
run** in advance so `/api/benchmark` and the telemetry panel already have data — and because
Hotdata's query worker scales to zero when idle, that also pre-warms it. A cold first query
stalls 10–20s; do not let that happen on stage.

---

### 0:00 — The problem (20s)

> "Emergencies don't happen one problem at a time. A wildfire is simultaneously a fire problem, a
> traffic problem, a hospital problem, a power problem, and a logistics problem. Incident command
> today works them mostly in sequence, and every minute of that is a minute of exposure."

### 0:20 — Sequential baseline (25s)

Run **sequential** mode. Let the cards light up one after another.

> "This is one agent at a time — the way a single-loop agent system would do it. Watch the cards:
> hazard, then evacuation, then medical. Note the wall clock."

Call out the measured number on screen.

### 0:45 — ResponseGrid, parallel (35s)

Run **parallel** mode. This is the moment.

> "Same five specialists. Same data. Same prompts. The only difference is the shape of the graph."

Point at the cards igniting together, then at the database ids:

> "Five agents live at once — and look at the database id on each card. Five *different* Hotdata
> databases, created for this run, each loaded with only that specialist's slice. The evacuation
> agent never sees hospital data. No lock contention, no stale reads, no agents queueing behind
> one warehouse."

### 1:20 — The merge (30s)

> "They finish and fan back into one Incident Commander."

Open the plan and go **straight to `resource_conflicts`** — this is the substance:

> "Here's what you only get from coordination. Generator 3 is the only 500kW unit on the incident.
> The infrastructure agent wants it for the hospital's surgical load. The evacuation agent wants
> it for the Sunset/PCH signal cluster keeping the corridor moving. Neither agent could see that
> conflict alone. The commander resolved it — hospital first, signals degrade to stop-controlled —
> and said why."

### 1:50 — Measured, not claimed (20s)

Show the big metric.

> "Parallel against sequential, both measured on real runs — nothing hard-coded. And it isn't just
> faster: it's the same work with the wall clock collapsed onto the critical path."

### 2:10 — Telemetry (25s)

Open the telemetry panel and run the queries **live**.

> "Every run today streamed into one persistent Hotdata database — this is live SQL against it, not
> a screenshot."

Show bottleneck, then the `config_version` comparison:

> "This told us the evacuation agent was the recurring critical path — it was the widest data slice.
> We narrowed it and bumped the config version. That's the before and after, in the same table.
> The telemetry didn't just watch the system, it told us what to fix."

### 2:35 — The unexpected (20s)

> "Emergencies don't follow demos. Give ResponseGrid something it hasn't seen."

Take a suggestion from the judges, or inject `road_blocked`.

> "Pacific Coast Highway just closed — the primary evacuation route."

> "ResponseGrid worked out which domains that actually invalidates — evacuation and logistics —
> and rerun *only those two*, on fresh databases with the new conditions. Hazard, medical and
> infrastructure keep their findings; no tokens wasted re-deriving what didn't change. New
> coordinated plan."

### 2:55 — Close (5s)

> "Emergencies don't happen one problem at a time. ResponseGrid doesn't solve them one at a time."

---

## If asked

- **"Is this real or mocked?"** — Real. RocketRide's engine runs the graph and the concurrency;
  Hotdata holds every agent's data. Every timing is wall-clock measured, every query latency is
  Hotdata's own `execution_time_ms`, every token count comes from the engine's counters. The
  scenario *data* is clearly-labelled simulation — every row is tagged `data_source: "simulated"`
  — because we won't present invented operational figures as historical fact.
- **"Why not one shared database?"** — Five agents against one table means lock contention and
  stale reads; Hotdata returns `409 RESOURCE_LOCKED` to a second concurrent writer. Per-agent
  databases remove that entirely, and each agent's slice is small so its queries stay fast.
- **"What if an agent fails?"** — It's marked `DEGRADED`, the commander merges the rest and says
  so in `degraded_agents`. A run degrades; it doesn't crash.
- **"Does it only do wildfires?"** — The schema is generic (`hazards`, `routes`, `facilities`,
  `utilities`, `resources`). Earthquake, flood, blackout, or mass-casualty is another scenario
  module; the agents and orchestration don't change.
- **"Cloud or local engine?"** — Local, running the identical RocketRide C++ runtime and the same
  `.pipe` files. Our Cloud API keys were rejected as invalid/revoked on the day, so we ran the
  engine ourselves; the pipelines are unchanged and run against Cloud as-is.
