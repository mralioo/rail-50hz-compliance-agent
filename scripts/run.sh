#!/usr/bin/env bash
# One-shot: check deps (incl. the Craftsman agent's FreeCAD engine), start
# the FastAPI backend if needed, then run the webapp (OmniDraft / GLEIS OS
# dashboard) in the foreground. Ctrl+C stops both cleanly — the backend is
# only started (and only killed) if this script started it; a backend
# already running on $PORT is left alone.
#
# FreeCAD is NOT a service you "start": the Craftsman agent shells out to
# FreeCADCmd headlessly, once per POST /jobs/{id}/craftsman call (see
# docs/CRAFTSMAN_AGENT.md) - there is no daemon to launch. This script only
# verifies FREECADCMD_PATH (backend/.env) resolves to a real binary, same
# as the other [ok]/[MISSING] dependency checks below.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
WEBAPP_DIR="$ROOT_DIR/webapp"
PORT="${PORT:-8000}"
WEBAPP_PORT="${WEBAPP_PORT:-5173}"
# 127.0.0.1, not localhost - uvicorn only binds IPv4 (see
# docs/CAD_VIEWER_INTEGRATION.md §6).
BASE_URL="http://127.0.0.1:${PORT}/api/v1"
LOG_FILE="$BACKEND_DIR/workdir/backend.log"

echo "== Dependency check =="

fail=0
if [ ! -x "$BACKEND_DIR/.venv/bin/python" ]; then
  echo "[MISSING] backend/.venv — run: make setup"
  fail=1
else
  echo "[ok] backend venv"
fi

if [ ! -d "$WEBAPP_DIR/node_modules" ]; then
  echo "[MISSING] webapp/node_modules — run: make webapp-install"
  fail=1
else
  echo "[ok] webapp node_modules"
fi

# Reuses the real lookup (app/craftsman/freecad_bridge.py) instead of
# re-guessing FREECADCMD_PATH/PATH resolution in bash.
if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  FREECAD_CHECK=$(cd "$BACKEND_DIR" && .venv/bin/python -c "
from app.craftsman.freecad_bridge import find_freecadcmd, find_worker
cmd, worker = find_freecadcmd(), find_worker()
print(f'{cmd or \"\"}|{worker or \"\"}')
" 2>/dev/null || echo "|")
  FREECAD_CMD="${FREECAD_CHECK%%|*}"
  FREECAD_WORKER="${FREECAD_CHECK##*|}"
  if [ -n "$FREECAD_CMD" ] && [ -n "$FREECAD_WORKER" ]; then
    echo "[ok] FreeCAD engine ($FREECAD_CMD)"
  else
    echo "[MISSING] FreeCADCmd not found — set FREECADCMD_PATH in backend/.env"
    echo "          (e.g. ../FreeCAD-pixi/build/debug/bin/FreeCADCmd). The"
    echo "          Craftsman agent (POST /jobs/{id}/craftsman) will 502"
    echo "          until this is set; everything else still works."
  fi
fi

if [ "$fail" -ne 0 ]; then
  echo
  echo "Fix the [MISSING] items above, then re-run this script."
  exit 1
fi

BACKEND_STARTED_BY_US=0
CLEANED_UP=0
cleanup() {
  if [ "$CLEANED_UP" -eq 1 ]; then
    return
  fi
  CLEANED_UP=1
  if [ "$BACKEND_STARTED_BY_US" -eq 1 ] && [ -n "${BACKEND_PID:-}" ]; then
    echo
    echo "[stopping] backend (pid $BACKEND_PID)"
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo
echo "== Backend =="

if curl -s --max-time 2 "$BASE_URL/health" >/dev/null 2>&1; then
  echo "[ok] backend already running on :$PORT"
else
  echo "[starting] backend on :$PORT (log: $LOG_FILE)"
  mkdir -p "$BACKEND_DIR/workdir"
  (cd "$BACKEND_DIR" && exec .venv/bin/uvicorn app.main:app --port "$PORT" >"$LOG_FILE" 2>&1) &
  BACKEND_PID=$!
  BACKEND_STARTED_BY_US=1
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
echo "== Dashboard (webapp) =="
echo "[starting] vite dev server on :$WEBAPP_PORT — Ctrl+C to stop everything"
echo

# Deliberately not `exec`'d: this script's own process (and its `cleanup`
# trap, which stops the backend it started) must stay alive after npm exits
# so Ctrl+C tears down both processes instead of leaving the backend
# orphaned - the exact failure mode found earlier during Craftsman testing.
(cd "$WEBAPP_DIR" && npm run dev -- --port "$WEBAPP_PORT")
