"""The engineer's console — sidebar (chat/findings/history/sketch/knowledge
base) wrapped around the bare cad-viewer export. See
docs/CAD_VIEWER_INTEGRATION.md.

Static HTML/CSS/JS asset, not templated (this repo has no Jinja2/bundler
anywhere) - two placeholder tokens are substituted at request time instead
of using Python f-strings, since the inline JS/CSS is full of `{}` braces
that would collide with f-string escaping.
"""
import json
from pathlib import Path

ASSET_PATH = Path(__file__).parent / "assets" / "console_shell.html"
UPLOAD_ASSET_PATH = Path(__file__).parent / "assets" / "console_upload.html"


def render_console_shell(job_id: str, filename: str) -> str:
    html = ASSET_PATH.read_text(encoding="utf-8")
    html = html.replace("__JOB_ID__", job_id)
    html = html.replace("__FILENAME_JSON__", json.dumps(filename))
    return html


def render_console_upload() -> str:
    """Job-id-less landing page: upload a real .dwg/.dxf, or pick a recent
    plan, then redirect into render_console_shell's page for that job."""
    return UPLOAD_ASSET_PATH.read_text(encoding="utf-8")
