"""Craftsman's FreeCAD bridge - subprocess adapter to the headless FreeCAD
worker (tools/freecad_worker/worker.py), the same shape as
`AcadSharpEngine._run` (app/adapters/cad/acadsharp_adapter.py): find the
external binary, shell out with a timeout, raise a typed error on failure.

Why the result is handed back as a `ParsedDrawing`, not a DXF file the
caller re-reads: hands-on testing found this FreeCAD build's own DXF
exporter drops layers and text (see tools/freecad_worker/worker.py's module
docstring and docs/CRAFTSMAN_AGENT.md). The worker extracts geometry/text
directly into this project's `Geometry`/`TextItem` shape instead, so the
caller can hand it straight to `AcadSharpEngine.write()` without a second,
lossy DXF round trip.
"""
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.domain.cad.ports import ParsedDrawing
from app.core.config import get_settings
from app.models.schemas import CraftsmanOp, Geometry, TextItem

RUN_TIMEOUT_S = 60
WORKER_RELATIVE_PATH = Path("tools/freecad_worker/worker.py")


class CraftsmanError(RuntimeError):
    """Raised when the FreeCAD worker can't be launched or reports failure."""


def find_freecadcmd() -> Path | None:
    settings = get_settings()
    if settings.freecadcmd_path and Path(settings.freecadcmd_path).expanduser().exists():
        return Path(settings.freecadcmd_path).expanduser()
    found = shutil.which("FreeCADCmd")
    return Path(found) if found else None


def find_worker() -> Path | None:
    from app.core.config import BACKEND_ROOT
    candidate = BACKEND_ROOT / WORKER_RELATIVE_PATH
    return candidate if candidate.exists() else None


def run_job(dxf_in: Path, ops: list[CraftsmanOp]) -> dict:
    """Runs the FreeCAD worker against `dxf_in`, returns its raw result dict
    (`op_results`/`layers`/`geometries`/`texts` - see worker.py)."""
    freecadcmd = find_freecadcmd()
    worker = find_worker()
    if not freecadcmd or not worker:
        raise CraftsmanError(
            "FreeCADCmd not available. Set FREECADCMD_PATH to a built FreeCAD "
            "(e.g. ../FreeCAD-pixi/build/debug/bin/FreeCADCmd) or put it on PATH."
        )
    with tempfile.TemporaryDirectory() as tmp:
        job_path = Path(tmp) / "job.json"
        result_path = Path(tmp) / "result.json"
        job = {
            "input": str(dxf_in),
            "ops": [op.model_dump(exclude_none=True) for op in ops],
        }
        job_path.write_text(json.dumps(job))

        # Paths travel via env vars, not argv - FreeCADCmd treats extra
        # positional args as documents to open through its own extension
        # dispatch (a `.json` arg gets handed to the Fem workbench's mesh
        # importer and crashes the process), confirmed hands-on.
        env = {
            **os.environ,
            "CRAFTSMAN_JOB_PATH": str(job_path),
            "CRAFTSMAN_RESULT_PATH": str(result_path),
        }
        proc = subprocess.run(
            [str(freecadcmd), str(worker)],
            capture_output=True, text=True, timeout=RUN_TIMEOUT_S, env=env,
        )
        if not result_path.exists():
            detail = (proc.stderr or proc.stdout or "").strip()[-800:]
            raise CraftsmanError(f"FreeCAD worker produced no result: {detail}")
        result = json.loads(result_path.read_text())

    if not result.get("ok", False):
        raise CraftsmanError(f"FreeCAD worker failed: {result.get('error')}")
    return result


def to_parsed_drawing(result: dict) -> ParsedDrawing:
    return ParsedDrawing(
        layers=result.get("layers", []),
        geometries=[Geometry(**g) for g in result.get("geometries", [])],
        texts=[TextItem(**t) for t in result.get("texts", [])],
    )
