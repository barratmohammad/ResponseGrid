# ResponseGrid frontend → backend integration

Frontend is in `frontend/`; the Python backend has not been modified.

## Launch

From the repository root:

- Stop any running frontend server before switching modes.
- `npm --prefix frontend run dev` — real API, proxied to `http://127.0.0.1:8000/api/*`.
- `npm --prefix frontend run dev:mock` — development-only synthetic events. Prominently labeled; excluded from benchmark claims.
- Open `http://127.0.0.1:5173/command`.
- `npm --prefix frontend run build` and `npm --prefix frontend test`.

Set `API_PROXY_TARGET` for another API origin. A production build can never enable mock events. No secrets go into frontend variables.

## Contract used

Based on Claude's project plan and current `backend/events.py`, `agents.py`, `schemas.py`, `main.py`, `orchestrator.py`, and `scenarios/palisades.py`. `CODEX_HANDOFF.md` was absent during initial implementation and was read in full when Claude created it; the final adapter matches that contract. HTTP payloads were reconciled against `main.py` after it landed.

- `GET /api/health`, `GET /api/scenarios` (list or `{scenarios: [...]}`).
- `POST /api/runs` with `{execution_mode: 'parallel' | 'sequential', scenario}` → `{run_id}` or `{id}`.
- `GET /api/runs/{run_id}/events`, named SSE events matching `backend/events.py`; numeric epoch-second timestamps and ISO timestamps supported. Replays deduplicated by run + seq; native EventSource reconnects; subscription closes on completed run/reset/unmount.
- `POST /api/runs/{run_id}/inject` sends `{type, payload: {target}}`. The API returns parent_run_id without a child ID, so the adapter polls `GET /api/runs` briefly to discover the matching parent_run_id/injected_event child, then attaches to its SSE replay. Backend mutations are fixed per type, so location fields are read-only. Other agents retain their results.
- `GET /api/telemetry/runs`, supports list, `{runs}`, or Hotdata `{columns, rows}` result. Only successful full measured runs with matching scenario/config are benchmarked.
- Agent IDs match Claude: hazard, evacuation, medical, infrastructure, logistics.
- Commander normalization accepts actual immediate_actions/action, resource_conflicts/resource/contenders/resolution, and unresolved_risks. Also accepts visual-development fixtures.

`src/adapter.ts` owns HTTP/SSE. `src/state.ts` normalizes events and metrics. `src/useIncident.ts` owns lifecycle; UI components don't call endpoints.

## Notes

The map is a labeled, self-contained geographic schematic, not a live navigation map. Static map assets are scenario illustration, not measured operational feeds. Injection visuals reflect the accepted condition; plan text always comes from events. The development sequence was browser-tested: parallel activation, coordinated plan, road closure with only traffic/logistics reassessing, plan delta, sequential single-agent activation, and reset. Eleven contract/state tests and the production build pass. Reset resets the frontend only, and intentionally leaves server jobs to complete their DB cleanup (no cancel endpoint exists yet).

Verified live: API/scenario discovery; Hotdata healthy; local RocketRide healthy. Actual inference is blocked by missing ANTHROPIC_API_KEY (reported by GET /api/health). Still needed after the key is configured: real end-to-end run/injection/reconnect verification. No frontend benchmark claims are populated from development fixtures.
