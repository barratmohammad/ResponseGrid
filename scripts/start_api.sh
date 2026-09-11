#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec ./.venv/bin/uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 "$@"
