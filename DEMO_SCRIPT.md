# ResponseGrid — 3-Minute Demo + Sponsor Close

**Before you walk up:** `./scripts/start_engine.sh`, `./scripts/start_api.sh`, then
`curl -s localhost:8000/api/health` (must be `ok: true`). Run **one parallel and one sequential
run** in advance so `/api/benchmark` and the telemetry panel already have data — and because
Hotdata's query worker scales to zero when idle, that also pre-warms it. A cold first query
stalls 10–20s; do not let that happen on stage.

**Frontend — run it in dev mode, and open the right URL:**

```bash
cd frontend && npm run dev      # NOT `preview`, NOT a static server
```

Then open **`http://127.0.0.1:5173/command`** directly and leave it loaded.

- `npm run dev` is required, not optional: `provider-plugin.ts` is a Vite **dev-server**
  middleware, so the `/weather`, `/closures` and `/connections` endpoints behind the live-feed
  panel exist only in dev. A production build serves the UI but those feeds 404.
- Go straight to `/command`. The app's entry route is a landing page, and Landing → `/home`
  → `/command` burns 15–20 seconds of a 180-second demo.
- Load it **before** you present. `App` is lazy-loaded behind a `Suspense` fallback — a
  1.1 MB chunk plus a 508 KB maplibre worker — so a cold hit shows "Loading command center…".
- Map tiles, fonts and terrain come from `demotiles.maplibre.org` and `elevation-tiles-prod`,
  and the live feeds call `api.weather.gov` and Caltrans. All need working venue wifi. Test on
  the real network; if it's bad, the map degrades and the plan + telemetry panels carry the demo.

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
> The medical agent wants it for St. John's surgical load. The infrastructure agent wants
> it for the Sunset/PCH signal cluster keeping the corridor moving. Neither agent could see that
> conflict alone. The commander resolved it — hospital first, signals degrade to stop-controlled —
> and said why."

### 1:50 — Measured, not claimed (20s)

Show the big metric. **Say the real number and its limits — do not oversell it.**

> "Sequential: 219 seconds. Parallel: 172. Same five agents, same data, same prompts — 1.27x.
> That's one run each on a laptop that's also hosting the engine, so treat it as directional.
> Our best parallel run was 66 seconds."

If a judge pushes on it, that's a good thing — tell them what we found:

> "Our first baseline was wrong in our favour. We chained the agents in one graph, and it
> came out *faster* than parallel. Turned out a chained agent doesn't treat the previous
> agent's lane output as its query, so four of five were doing no work at all — zero
> queries. We caught it in the telemetry, threw the number away, and rebuilt the baseline
> as the same single-agent work run serially."

### 2:10 — Telemetry (25s)

Open the telemetry panel and run the queries **live**.

> "Every run today streamed into one persistent Hotdata database — this is live SQL against it, not
> a screenshot."

Show bottleneck, then the `config_version` comparison:

> "This told us the logistics agent was struggling with the widest data slice, four tables,
> and was burning its wave budget discovering them instead of answering. We narrowed it
> to the two tables it reasons over and bumped the config version. That's the before and
> after, in the same table. The telemetry didn't just watch the system, it told us what to fix."

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


### 3:00 — Our sponsors (40s)

Keep the coordinated plan on screen, then point to the specialist database IDs and telemetry.

> "To close, here's how we use our two sponsors. RocketRide powers the orchestration:
> its pipeline graphs run our five specialist agents in parallel, then a separate
> Incident Commander pipeline combines their findings and resolves resource conflicts.
> When conditions change, we rerun only the affected specialists before updating the plan."

> "Hotdata powers the data layer. Each specialist queries its own temporary database,
> loaded with the scenario data relevant to its role. We create and load those databases
> before each run and clean them up afterward. A separate, persistent Hotdata database
> stores telemetry so we can investigate failures and compare performance.
> Thank you to RocketRide and Hotdata for supporting the project!"

**GitHub:** https://github.com/barratmohammad/ResponseGrid

---

## If asked

- **"Is this real or mocked?"** — Real. RocketRide's engine runs the graph and the concurrency;
  Hotdata holds every agent's data. Every timing is wall-clock measured, every query latency is
  Hotdata's own `execution_time_ms`. Token accounting is reported as unavailable, not estimated —
  the local engine didn't populate those counters on these runs, and we won't invent a figure. The
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
