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

The map uses MapLibre with actual USGS topographic and imagery basemaps, contour lines, and Terrarium elevation tiles for optional 3D terrain. Tiles require internet access; the MapLibre worker is bundled explicitly by Vite for development and production. Incident polygons and facility markers are approximate simulation overlays, not live emergency feeds. The redesigned interface prioritizes the map and readable recommendations, with specialist cards below and detailed telemetry in an expandable drawer. Injection visuals reflect the accepted condition; plan text always comes from events. The development sequence was browser-tested: parallel activation, coordinated plan, road closure with only traffic/logistics reassessing, plan delta, sequential single-agent activation, and reset. Eleven contract/state tests and the production build pass. Reset resets the frontend only, and intentionally leaves server jobs to complete their DB cleanup (no cancel endpoint exists yet).

Verified live: API/scenario discovery; Hotdata healthy; local RocketRide healthy. Actual inference is blocked by missing ANTHROPIC_API_KEY (reported by GET /api/health). Still needed after the key is configured: real end-to-end run/injection/reconnect verification. No frontend benchmark claims are populated from development fixtures.

## Control tower expansion

`ControlTower.tsx` adds situation, asset inventory, exercise notification ledger, editable media bulletin, provider status, and the existing commander plan. A/B/C zone selection changes conceptual egress arrows. Road and hazard injections withhold affected candidate routes. Notification and media assistants are local templates, not new backend LLM agents. No SMS is transmitted.

`public/data/infrastructure.json` is a downloaded OpenStreetMap inventory in bbox 34.00,-118.63,34.14,-118.43 (8 hospital features, 19 fire-service features including helispots, 88 power segments). Features are not a deduplicated official facility registry; unknown capacities, energization and road status remain unknown. `scripts/build-infrastructure.py` converts Overpass geometry/bounds to map features. USGS imagery is archival, not live satellite surveillance.

`provider-plugin.ts` adds a localhost-only Vite development bridge: GET `/ops-api/weather` (NWS active alerts at the incident center), `/ops-api/closures` (Caltrans District 7 LCS filtered to the response area), `/ops-api/connections` (credential presence only). Each public fetch has an 18-second timeout and 60-second cache. Closure records distinguish reported active, ended, and scheduled/unconfirmed; absence never means a road is open. Marker popups show source timestamps and scheduling. Weather/closure cards poll while visible; closure markers poll every minute.

Production build does NOT include this server bridge. Move these read-only handlers into the backend before hosting. No utility/AVL/CAD/siren integration exists. Twilio variables in `.env.example` are server-only setup placeholders; credentials have not been supplied or validated. Real messaging still requires approved recipients, send endpoints and signed delivery callbacks. Do not treat demo receipts as real delivery confirmation.

The Sources panel has a six-second browser-only audible alarm test with silence/acknowledge. External sirens are not activated. Build and 14 contract/state/routing tests pass.

## Street movement and fullscreen

Map toolbar Full screen enters the browser Fullscreen API (fixed viewport fallback); Escape or Exit full screen restores the dashboard. `MapSimulation.tsx` has play/pause, restart, 1x/2x/4x playback and a per-zone fictional notification progression, synchronized with the tower summary. Resident cars and two fire engines interpolate along connected OSM street geometry, rather than straight endpoint chords. `scripts/build-motion.py` derives directed routes from the downloaded Overpass node graph, respecting mapped one-way tags. `public/data/motion-routes.json` retains named street sequences. This is an accelerated visual exercise, not a calibrated traffic model or approved evacuation routing. On a scenario route hold, affected vehicles stop moving. Power and generic-road overlays default off; facilities have compact vector symbols. Sixteen tests and the production build pass.

Expanded exercise: 13 civilian routes with 286 cars and 8 distinct engine/truck assignments. Routing graph now includes 602 residential OSM ways, with paths through neighborhood feeder streets. Fire stations use blue building/garage vector icons, never flames. Power inventory is visible by default. Three fictional blackout polygons activate at 25/65/110 playback seconds (240/380/170 affected homes), and the fire perimeter gradually expands by up to 12% in linear extent over the 180-second exercise. Pause freezes progression; restart clears it. The condition HUD labels all outage/fire evolution as simulated. Seventeen tests pass.

Facility finder: map-level Hospitals / Fire stations buttons list all 8 hospital and 19 fire-service inventory features with category icons. Selecting an item flies to it and opens its popup; Show all restores the regional view. Larger cross/building markers reveal name labels on hover/focus. Inventory can include helispots or overlapping features, and is not an exhaustive official registry. Movement now includes 21 resident routes × 24 cars = 504 cars and 16 individually named fire apparatus routes. Build and 17 tests pass.


## Continuous dispatch and electrical network update

Fire station markers and legends now use a shared generic Maltese-cross fire-service badge (`FireBadge.tsx`), not an official agency seal. All 16 apparatus routes include connected return paths built from the directed street graph. Playback no longer stops at 180 seconds or clamps engines at route endpoints: outbound/return dispatch cycles continue, with repeated civilian waves. Hazard expansion and notification totals remain bounded. `playback.test.ts` verifies continued motion past three minutes and endpoint continuity for every engine return route.

All 88 mapped electrical line segments now have a prominent purple stroke and white halo, visible by default. Power network opens an electrical legend and regional-network view. Green polygons represent simulated powered areas; dark polygons represent staged exercise outages. A Santa Monica powered area remains visible after the three outages activate. Actual line energization is unknown and inventory coverage is incomplete; the inspector explicitly distinguishes mapped geometry from simulated states.

Validation: 19 tests pass; production build passes after the final powered-area addition. Browser inspection confirms fire-service badges, purple lines, green power area and the electrical inspector render on localhost.

## App entry and demo workspace

`Platform.tsx` now owns the entry routes: `/` marketing landing, `/product` capabilities and readiness, `/signin` local demo session, `/home` demo workspace and three-step walkthrough, `/command` existing command center. Unknown paths render a recovery page. Native links support history and direct Vite entry; production hosting must rewrite these paths to index.html. `platform.css` scopes the new responsive visual system away from command center styles. The command center has workspace navigation and local session exit.

Demo sign-in stores a display name in sessionStorage, never credentials. Guest access remains available. This is not production authentication, an authorization boundary or a real account system. Production identity-provider integration and backend session authorization remain future work. The product readiness section explains current integration boundaries. New pages use vector terrain artwork with no additional network assets. Build and all 19 existing tests pass.

Sign-in simplified per user request: one-click “Sign in to demo,” optional display name, default “Demo operator.” No real account required. Command center code now loads lazily, reducing the landing entry JavaScript bundle to approximately 247 kB before gzip. Final production build passes.
