"""In-memory debug telemetry - every HTTP request and every Craftsman op,
kept in small ring buffers so the webapp's Debug Console (see
docs/CRAFTSMAN_AGENT.md's debug-mode section) can show live traffic/command
history without a real logging stack. Same durability level as the rest of
this POC's in-memory state - resets on backend restart, that's fine, it's
for watching *this* dev session, not an audit trail.
"""
import threading
from collections import deque
from datetime import datetime, timezone

_MAX_ENTRIES = 300


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DebugLog:
    def __init__(self) -> None:
        self._requests: deque[dict] = deque(maxlen=_MAX_ENTRIES)
        self._commands: deque[dict] = deque(maxlen=_MAX_ENTRIES)
        self._lock = threading.Lock()

    def record_request(self, method: str, path: str, status: int, duration_ms: float) -> None:
        with self._lock:
            self._requests.appendleft({
                "ts": _now_iso(),
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": round(duration_ms, 1),
            })

    def record_command(
        self, job_id: str, transport: str, op: str, ok: bool, detail: str,
    ) -> None:
        with self._lock:
            self._commands.appendleft({
                "ts": _now_iso(),
                "job_id": job_id,
                "transport": transport,  # "headless" | "live"
                "op": op,
                "ok": ok,
                "detail": detail,
            })

    def requests(self) -> list[dict]:
        with self._lock:
            return list(self._requests)

    def commands(self) -> list[dict]:
        with self._lock:
            return list(self._commands)


debug_log = DebugLog()
