"""Craftsman "live" mode - manages a persistent, visible FreeCAD GUI session
streamed into the browser via xpra's HTML5 client, instead of the one-shot
headless subprocess `freecad_bridge.py` uses. See
tools/freecad_worker/live_session.py (runs inside the GUI process) and
docs/CRAFTSMAN_AGENT.md.

v1 scope, deliberately: **one global session**, not per-job/multi-tenant -
starting a new job's live session tears down any previous one first. This
is a hackathon demo watched by one engineer at a time, not a concurrent
multi-user product; per-session display/port allocation is real, bounded
work this doesn't need yet.
"""
import http.client
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

from app.core.config import get_settings
from app.craftsman.freecad_bridge import CraftsmanError

LIVE_SESSION_RELATIVE_PATH = Path("tools/freecad_worker/live_session.py")
STARTUP_TIMEOUT_S = 25
SHUTDOWN_TIMEOUT_S = 10
OP_TIMEOUT_S = 60


def find_freecad_gui() -> Path | None:
    settings = get_settings()
    if settings.freecad_gui_path and Path(settings.freecad_gui_path).expanduser().exists():
        return Path(settings.freecad_gui_path).expanduser()
    found = shutil.which("FreeCAD")
    return Path(found) if found else None


def find_xpra() -> Path | None:
    settings = get_settings()
    if settings.xpra_path and Path(settings.xpra_path).expanduser().exists():
        return Path(settings.xpra_path).expanduser()
    found = shutil.which("xpra")
    return Path(found) if found else None


def find_live_session_script() -> Path | None:
    from app.core.config import BACKEND_ROOT
    candidate = BACKEND_ROOT / LIVE_SESSION_RELATIVE_PATH
    return candidate if candidate.exists() else None


class LiveSession:
    def __init__(self, job_id: str, proc: subprocess.Popen, display: str, html_url: str, op_port: int):
        self.job_id = job_id
        self.proc = proc
        self.display = display
        self.html_url = html_url
        self.op_port = op_port
        self.started_at = time.monotonic()


_current: LiveSession | None = None
_lock = threading.Lock()


def current_job_id() -> str | None:
    with _lock:
        return _current.job_id if _current else None


def session_status() -> dict | None:
    """Feeds the Debug Console's "Live session" panel - real process/port
    health, not just "a session object exists" (see docs/CRAFTSMAN_AGENT.md's
    debug-mode section)."""
    with _lock:
        session = _current
    if session is None:
        return None
    settings = get_settings()
    return {
        "job_id": session.job_id,
        "display": session.display,
        "pid": session.proc.pid,
        "process_alive": session.proc.poll() is None,
        "uptime_s": round(time.monotonic() - session.started_at, 1),
        "op_port": session.op_port,
        "op_port_open": _wait_for_port(session.op_port, 0.5),
        "html_port": settings.craftsman_live_html_port,
        "html_ready": _wait_for_html_ready(settings.craftsman_live_html_port, 0.5),
        "html_url": session.html_url,
    }


def _wait_for_port(port: int, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _wait_for_port_closed(port: int, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                pass
            time.sleep(0.3)
        except OSError:
            return True
    return False


def _wait_for_html_ready(port: int, timeout_s: float) -> bool:
    """A raw TCP connect succeeding only proves xpra's listener is bound -
    not that its HTTP/WebSocket handling is actually up yet (confirmed
    hands-on: the browser's WebSocket upgrade would stall indefinitely at
    "Opening WebSocket connection" against a session whose op port was
    already accepting connections but whose html/WS server evidently wasn't
    fully ready). A real HTTP GET that gets a real response is a much
    stronger readiness signal."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            try:
                conn.request("GET", "/")
                resp = conn.getresponse()
                resp.read()
                if resp.status < 500:
                    return True
            finally:
                conn.close()
        except (OSError, http.client.HTTPException):
            pass
        time.sleep(0.5)
    return False


def start_live_session(job_id: str, dxf_path: Path) -> str:
    """Stops any existing live session, starts a new one for `job_id`
    against `dxf_path`, returns the xpra HTML5 client URL to embed in an
    iframe. Raises CraftsmanError if the GUI binary/xpra aren't configured
    or the session fails to come up in time."""
    settings = get_settings()
    freecad_gui = find_freecad_gui()
    xpra = find_xpra()
    live_session = find_live_session_script()
    if not freecad_gui or not xpra or not live_session:
        raise CraftsmanError(
            "Live FreeCAD mode not available. Set FREECAD_GUI_PATH and XPRA_PATH "
            "(see backend/tools/freecad_worker/live_env/setup.sh) or put them on PATH."
        )

    stop_live_session()

    display = settings.craftsman_live_display
    op_port = settings.craftsman_live_op_port
    html_port = settings.craftsman_live_html_port

    env = {
        **os.environ,
        # xpra shells out to its own bundled Xvfb by bare name (`Xvfb ...`),
        # which lives in the same pixi env as the xpra binary itself - not
        # necessarily on the caller's PATH, so prepend it.
        "PATH": f"{xpra.parent}:{os.environ.get('PATH', '')}",
        "CRAFTSMAN_LIVE_INPUT": str(dxf_path),
        "CRAFTSMAN_LIVE_PORT": str(op_port),
    }
    cmd = [
        str(xpra), "start", display,
        f"--start-child={freecad_gui} {live_session}",
        "--exit-with-children=yes",
        "--daemon=no",
        "--html=on",
        f"--bind-tcp=0.0.0.0:{html_port}",
    ]
    # Logged to a file, not DEVNULL - a silent startup failure here (bad
    # binary path, port conflict, X/GL error) is otherwise very hard to
    # diagnose, confirmed hands-on while building this.
    log = open(settings.work_dir / "craftsman_live_xpra.log", "w")
    proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)

    if not _wait_for_port(op_port, STARTUP_TIMEOUT_S):
        proc.terminate()
        raise CraftsmanError(
            f"Live FreeCAD session didn't come up within {STARTUP_TIMEOUT_S}s "
            "(op socket never opened) - check FREECAD_GUI_PATH/XPRA_PATH, that "
            "backend/tools/freecad_worker/live_env/setup.sh has been run, and "
            f"{settings.work_dir / 'craftsman_live_xpra.log'} for the real error."
        )
    # The op port opening only proves live_session.py's own accept thread is
    # up - xpra's HTML5/WebSocket server is a separate process-internal
    # component that isn't guaranteed ready at the same moment (confirmed
    # hands-on: a client embedded before this settled would connect its
    # WebSocket but stall forever mid-handshake, never erroring visibly).
    if not _wait_for_html_ready(html_port, STARTUP_TIMEOUT_S):
        proc.terminate()
        raise CraftsmanError(
            f"Live FreeCAD session's HTML5 client didn't come up within "
            f"{STARTUP_TIMEOUT_S}s - check {settings.work_dir / 'craftsman_live_xpra.log'}."
        )

    html_url = f"http://localhost:{html_port}/"
    global _current
    with _lock:
        _current = LiveSession(job_id, proc, display, html_url, op_port)
    return html_url


def send_live_op(ops: list[dict]) -> dict:
    """Sends `ops` (already-dumped CraftsmanOp dicts) to the running live
    session's op socket, returns the same shape as freecad_bridge.run_job's
    result dict. Raises CraftsmanError if no session is running or the
    session doesn't respond."""
    with _lock:
        session = _current
    if session is None or session.proc.poll() is not None:
        raise CraftsmanError("No live FreeCAD session is running - call live/start first.")

    try:
        with socket.create_connection(("127.0.0.1", session.op_port), timeout=OP_TIMEOUT_S) as s:
            s.sendall(json.dumps({"ops": ops}).encode("utf-8"))
            s.shutdown(socket.SHUT_WR)
            chunks = []
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
        result = json.loads(b"".join(chunks).decode("utf-8"))
    except OSError as exc:
        raise CraftsmanError(f"Live FreeCAD session unreachable: {exc}") from exc

    if not result.get("ok", False):
        raise CraftsmanError(f"Live FreeCAD op failed: {result.get('error')}")
    return result


def stop_live_session() -> None:
    """Tears down the current live session, if any, and waits for its ports
    to actually free up before returning - not just for `xpra stop`/the
    process to exit. Without this, `start_live_session`'s next `xpra start
    --bind-tcp=...` on the same port can race a not-yet-fully-released old
    listener (confirmed hands-on as a real, repeatable cause of the
    stuck-at-"Opening WebSocket connection" symptom - the old and new
    session's sockets on the same port overlapping for a moment is enough
    to leave a client's very first connection attempt in a broken half-open
    state that never recovers). Safe to call when nothing is running."""
    global _current
    with _lock:
        session, _current = _current, None
    if session is None:
        return
    xpra = find_xpra()
    if xpra:
        subprocess.run(
            [str(xpra), "stop", session.display],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
        )
    if session.proc.poll() is None:
        session.proc.terminate()
        try:
            session.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            session.proc.kill()
    _wait_for_port_closed(session.op_port, SHUTDOWN_TIMEOUT_S)
    _wait_for_port_closed(get_settings().craftsman_live_html_port, SHUTDOWN_TIMEOUT_S)
