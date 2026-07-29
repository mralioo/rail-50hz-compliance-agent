#!/usr/bin/env bash
# One-shot: check deps, start backend if needed, and open the browser
# console. With no FILE given, opens the upload landing page so you can
# drag-and-drop any real .dwg/.dxf yourself; with FILE=path/to/plan.dwg,
# uploads that file and jumps straight to its console. See
# docs/CAD_VIEWER_INTEGRATION.md §6/§9.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
PORT="${PORT:-8000}"
# 127.0.0.1, not localhost: uvicorn only binds IPv4, and some browsers try
# the ::1 (IPv6) resolution of "localhost" first and fail before falling
# back — see docs/CAD_VIEWER_INTEGRATION.md §6.
BASE_URL="http://127.0.0.1:${PORT}/api/v1"
LOG_FILE="$BACKEND_DIR/workdir/backend.log"
FILE="${FILE:-}"

# node/dotnet installed user-space outside the default PATH in this env
export PATH="$HOME/nodejs/bin:$HOME/.dotnet:$PATH"

echo "== Dependency check =="

fail=0
if [ ! -x "$BACKEND_DIR/.venv/bin/python" ]; then
  echo "[MISSING] backend/.venv — run: make setup"
  fail=1
else
  echo "[ok] backend venv"
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[MISSING] node on PATH (expected ~/nodejs/bin or system PATH)"
  fail=1
else
  echo "[ok] node ($(node --version))"
fi

CLI_JS="$BACKEND_DIR/tools/cad_viewer_cli/node_modules/@mlightcad/cad-html-exporter-cli/dist/cli.js"
if [ ! -f "$CLI_JS" ]; then
  echo "[MISSING] cad-viewer exporter CLI — run:"
  echo "    cd backend/tools/cad_viewer_cli && npm install && npx playwright install chromium"
  fail=1
else
  echo "[ok] cad-viewer exporter CLI"
fi

if [ ! -d "$HOME/.cache/ms-playwright" ]; then
  echo "[MISSING] Playwright browser cache — run:"
  echo "    cd backend/tools/cad_viewer_cli && npx playwright install chromium"
  fail=1
else
  echo "[ok] Playwright chromium cache"
fi

if [ -n "$FILE" ] && [ ! -f "$FILE" ]; then
  echo "[MISSING] FILE=$FILE does not exist"
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  echo
  echo "Fix the [MISSING] items above, then re-run this script."
  exit 1
fi

echo
echo "== Backend =="

if curl -s --max-time 2 "$BASE_URL/health" >/dev/null 2>&1; then
  echo "[ok] backend already running on :$PORT"
else
  echo "[starting] backend on :$PORT (log: $LOG_FILE)"
  mkdir -p "$BACKEND_DIR/workdir"
  (cd "$BACKEND_DIR" && nohup .venv/bin/uvicorn app.main:app --port "$PORT" >"$LOG_FILE" 2>&1 &)
  for i in $(seq 1 30); do
    if curl -s --max-time 1 "$BASE_URL/health" >/dev/null 2>&1; then
      echo "[ok] backend healthy after ${i}s"
      break
    fi
    sleep 1
    if [ "$i" -eq 30 ]; then
      echo "[FAIL] backend did not become healthy — check $LOG_FILE"
      exit 1
    fi
  done
fi

echo
echo "== Console =="

if [ -n "$FILE" ]; then
  JOB_ID=$(curl -s -F "file=@$FILE" "$BASE_URL/jobs" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
  echo "[ok] job created from $FILE: $JOB_ID"

  echo -n "[waiting] pipeline"
  for i in $(seq 1 30); do
    STATUS=$(curl -s "$BASE_URL/jobs/$JOB_ID" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
    if [ "$STATUS" = "ready" ]; then
      echo " -> ready"
      break
    fi
    if [ "$STATUS" = "failed" ]; then
      echo " -> FAILED"
      exit 1
    fi
    echo -n "."
    sleep 1
    if [ "$i" -eq 30 ]; then
      echo " -> timeout waiting for job to become ready (last status: $STATUS)"
      exit 1
    fi
  done
  TARGET_URL="$BASE_URL/jobs/$JOB_ID/console"
else
  TARGET_URL="$BASE_URL/console"
  echo "[ok] no FILE given — opening the upload page (drag/drop or pick a .dwg/.dxf yourself)"
  echo "     (or re-run as: make viewer FILE=path/to/your.dwg)"
fi

echo "URL: $TARGET_URL"

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$TARGET_URL" >/dev/null 2>&1 &
  echo "[opened] in default browser"
elif command -v sensible-browser >/dev/null 2>&1; then
  sensible-browser "$TARGET_URL" >/dev/null 2>&1 &
  echo "[opened] in default browser"
else
  echo "[manual] no xdg-open/sensible-browser found — open the URL above yourself"
fi
