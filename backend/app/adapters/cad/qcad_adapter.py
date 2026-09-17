"""QCAD adapter - shells out to `qcadcmd` (QCAD's headless console binary)
running the ECMAScript connector scripts in tools/qcad_connector/, the same
subprocess pattern as ACadSharp's CLI wrapper.

DXF only. QCAD's open-source tree has no DWG import/export module at all
(confirmed by inspecting src/io/ - only dxf/, built on the bundled dxflib);
DWG is a closed-source QCAD Professional feature. See
docs/QCAD_CONNECTOR.md for the full investigation, including the finding
that QCAD's DXF writer only actually distinguishes R12 vs R2000/AC1015
internally today - other version labels don't change the output.

Unbuilt in this environment (no Qt6, no root - see docs/QCAD_CONNECTOR.md
section 6). This adapter is scaffolding: correct against QCAD's documented
and source-grounded scripting API, not yet exercised against a real
`qcadcmd` binary. Treat `find_qcadcmd()`'s search paths as best-effort until
someone builds it and confirms the actual binary location.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.domain.cad.ports import CadEnginePort, EngineError, ParsedDrawing
from app.models.schemas import Geometry, TextItem

RUN_TIMEOUT_S = 60
READ_SCRIPT = Path("tools/qcad_connector/read.js")
WRITE_SCRIPT = Path("tools/qcad_connector/write.js")


def find_qcadcmd() -> Path | None:
    settings = get_settings()
    if settings.qcadcmd_path and Path(settings.qcadcmd_path).expanduser().exists():
        return Path(settings.qcadcmd_path).expanduser()
    for name in ("qcadcmd.com", "qcadcmd"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


class QCadEngine(CadEnginePort):
    name = "qcad"
    open_source = True  # GPLv3 (community edition) - invoked as a subprocess,
    # never linked, so the GPL's linking terms don't reach this codebase; see
    # docs/QCAD_CONNECTOR.md section 2.
    reads_dwg = False
    reads_dxf = True
    writes_dwg = False
    writes_dxf = True

    def _run(self, script: Path, extra_args: list[str]) -> subprocess.CompletedProcess:
        qcadcmd = find_qcadcmd()
        if not qcadcmd:
            raise EngineError(
                "qcadcmd not available. Build QCAD (needs Qt6 + CMake/Ninja, see "
                "docs/QCAD_CONNECTOR.md section 6) and set QCADCMD_PATH to the "
                "resulting qcadcmd(.com) binary, or put it on PATH."
            )
        from app.core.config import BACKEND_ROOT
        script_path = BACKEND_ROOT / script
        result = subprocess.run(
            [
                str(qcadcmd), "-no-gui", "-platform", "offscreen",
                "-autostart", str(script_path), *extra_args, "-quit",
            ],
            capture_output=True, text=True, timeout=RUN_TIMEOUT_S,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()[-800:]
            raise EngineError(f"qcad {script.name} failed: {detail}")
        return result

    def read(self, path: Path) -> ParsedDrawing:
        with tempfile.TemporaryDirectory() as tmp:
            out_json = Path(tmp) / "out.json"
            self._run(READ_SCRIPT, [str(path), str(out_json)])
            if not out_json.exists():
                raise EngineError(f"qcad read produced no output for {path}")
            data = json.loads(out_json.read_text())
        if "error" in data:
            raise EngineError(f"qcad read: {data['error']}")
        return ParsedDrawing(
            layers=data.get("layers", []),
            geometries=[Geometry(**g) for g in data.get("geometries", [])],
            texts=[TextItem(**t) for t in data.get("texts", [])],
        )

    def write(self, drawing: ParsedDrawing, out_path: Path, version: str = "r2000") -> Path:
        spec = {
            "layers": drawing.layers,
            "geometries": [g.model_dump() for g in drawing.geometries],
            "texts": [t.model_dump() for t in drawing.texts],
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(spec))
            self._run(WRITE_SCRIPT, [str(spec_path), str(out_path), version])
        return out_path
