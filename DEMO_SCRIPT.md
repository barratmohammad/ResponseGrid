# ResponseGrid — Short Demo Walkthrough

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

### Opening — What I built

Show the command-center map with a completed run ready to inspect.

> "Hey everyone! I built ResponseGrid, an AI emergency-response prototype using a simulated
> wildfire scenario. Five specialists assess hazards, evacuation, medical needs,
> infrastructure, and logistics, then an Incident Commander combines their findings
> into one coordinated plan."

### Sponsor 1 — RocketRide

Point to the five specialist cards, then open the coordinated plan.

> "Our first sponsor, RocketRide, handles the orchestration. Its pipeline graphs run
> the five specialist agents in parallel. We then pass their findings together into a
> separate commander pipeline to resolve resource conflicts and produce the shared plan."

### Sponsor 2 — Hotdata

Show the specialist database IDs and the telemetry panel.

> "Our second sponsor, Hotdata, provides the data layer. Each specialist queries its
> own temporary database containing the scenario data relevant to its role. We create
> and load those databases before the run, then clean them up afterward. A separate,
> persistent Hotdata database keeps telemetry for debugging and performance comparisons."

### Changing conditions

Inject `road_blocked` and point to evacuation and logistics reassessing. Updating the
plan may take longer than the narration; use a prepared completed example if needed.

> "When conditions change, like a road closure, ResponseGrid reruns only the affected
> specialists using fresh Hotdata databases. RocketRide runs those reassessments and
> the commander workflow to update the coordinated plan."

### Close

> "Together, RocketRide and Hotdata power parallel analysis, focused data access, and
> coordinated updates. The code is on GitHub, and I'd love feedback on the agent
> coordination and per-agent database approach!"

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
