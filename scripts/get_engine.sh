#!/usr/bin/env bash
# Fetch the RocketRide engine runtime (not vendored into git -- ~850MB extracted).
#
# We run the engine locally rather than on RocketRide Cloud because our Cloud API
# keys were rejected as "Invalid or revoked API key" during the event. It is the
# same C++ runtime and the same .pipe files either way; only ROCKETRIDE_URI changes.
#
# Note: the linux-x64 image cannot bootstrap on Apple Silicon -- it resolves
# onnxruntime-gpu==1.20.1, which has no matching wheel. The darwin-arm64 build
# excludes that dependency by platform marker, so use the native build on macOS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="${1:-server-v3.3.0-prerelease}"   # this tag ships the db_hotdata node (143 nodes)
DEST="$ROOT/engine2"

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) ASSET="darwin-arm64.tar.gz" ;;
  Linux-x86_64) ASSET="linux-x64.tar.gz" ;;
  *) echo "unsupported platform: $(uname -s)-$(uname -m)"; exit 1 ;;
esac

URL=$(curl -fsSL "https://api.github.com/repos/rocketride-org/rocketride-server/releases/tags/$TAG" \
      | python3 -c "import json,sys;print(next(a['browser_download_url'] for a in json.load(sys.stdin)['assets'] if a['name'].endswith('$ASSET')))")

mkdir -p "$ROOT/.cache" "$DEST"
echo "downloading $TAG ($ASSET)..."
curl -fL "$URL" -o "$ROOT/.cache/rr-engine.tar.gz"
tar -xzf "$ROOT/.cache/rr-engine.tar.gz" -C "$DEST"
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true

# The bundle omits PyJWT on some builds; the task module imports it at startup.
"$DEST/bin/uv" pip install -q --target "$DEST/lib/python3.12/site-packages" PyJWT 2>/dev/null \
  || "$ROOT/.venv/bin/python" -m pip install -q --target "$DEST/lib/python3.12/site-packages" PyJWT 2>/dev/null \
  || true

echo "engine ready in $DEST  ($(ls "$DEST/nodes" | wc -l | tr -d ' ') nodes)"
[ -e "$DEST/nodes/db_hotdata" ] && echo "db_hotdata node: present" || echo "WARNING: db_hotdata missing in $TAG"
