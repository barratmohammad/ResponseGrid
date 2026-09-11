#!/usr/bin/env bash
# Start the local RocketRide engine with the env the pipes reference.
# The engine resolves ${VAR} in .pipe config from ITS OWN environment, and
# db_hotdata falls back to HOTDATA_API_KEY / HOTDATA_WORKSPACE.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
set -a; source .env; set +a
export HOTDATA_WORKSPACE="${HOTDATA_WORKSPACE_ID:-}"     # node expects this name
export ROCKETRIDE_ANTHROPIC_KEY="${ANTHROPIC_API_KEY:-}"
pkill -f "engine ./ai/eaas.py" 2>/dev/null || true
sleep 1
cd "$ROOT/engine2"
nohup ./engine ./ai/eaas.py --host=127.0.0.1 > "$ROOT/.cache/engine.log" 2>&1 &
echo "engine pid $!"
for i in $(seq 1 60); do
  if nc -z localhost 5565 2>/dev/null; then echo "engine listening on 5565 (~$((i*2))s)"; exit 0; fi
  pgrep -f "engine ./ai/eaas.py" >/dev/null || { echo "ENGINE DIED:"; tail -20 "$ROOT/.cache/engine.log"; exit 1; }
  sleep 2
done
echo "TIMEOUT waiting for engine"; tail -20 "$ROOT/.cache/engine.log"; exit 1
