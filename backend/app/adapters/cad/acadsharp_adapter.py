"""ACadSharp adapter - shells out to `tools/acadsharp_cli` (a thin .NET
console wrapper around https://github.com/DomCR/ACadSharp), the same
subprocess pattern already used for LibreDWG's dwg2dxf/dxf2dwg.

Why a subprocess and not a Python binding: ACadSharp is .NET/C#, this
backend is Python. Shelling out to a small, purpose-built CLI (source in
tools/acadsharp_cli/Program.cs) is simpler and lower-risk than a
Python<->.NET bridge (pythonnet) for what is currently an experiment, not a
committed dependency - see docs/CAD_ENGINE_FRAMEWORK.md.

Unlike LibreDWG, ACadSharp reads AND writes DWG natively - no DXF
intermediate step, no composition needed. Hands-on results (same doc):
identical entity counts to the LibreDWG+ezdxf pipeline on the real reference
plan, and its DWG writes round-trip cleanly through a *third*, independent
implementation (LibreDWG's own dwg2dxf).
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
CLI_RELATIVE_PATH = Path("tools/acadsharp_cli/bin/Release/net8.0/acadsharp_cli.dll")


def find_dotnet() -> Path | None:
    settings = get_settings()
    if settings.dotnet_path and Path(settings.dotnet_path).expanduser().exists():
        return Path(settings.dotnet_path).expanduser()
    found = shutil.which("dotnet")
    if found:
        return Path(found)
    local = Path.home() / ".dotnet" / "dotnet"
    return local if local.exists() else None


def find_cli() -> Path | None:
    settings = get_settings()
    if settings.acadsharp_cli_path and Path(settings.acadsharp_cli_path).expanduser().exists():
        return Path(settings.acadsharp_cli_path).expanduser()
    from app.core.config import BACKEND_ROOT
    candidate = BACKEND_ROOT / CLI_RELATIVE_PATH
    return candidate if candidate.exists() else None


class AcadSharpEngine(CadEnginePort):
    name = "acadsharp"
    open_source = True  # MIT-licensed
    reads_dwg = True
    reads_dxf = True
    writes_dwg = True
    writes_dxf = True

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        dotnet = find_dotnet()
        cli = find_cli()
        if not dotnet or not cli:
            raise EngineError(
                "ACadSharp CLI not available. Build it: cd backend/tools/acadsharp_cli "
                "&& dotnet build -c Release (needs the .NET 8 SDK; DOTNET_PATH/ACADSHARP_CLI_PATH "
                "to point elsewhere if not auto-detected)."
            )
        result = subprocess.run(
            [str(dotnet), str(cli), *args],
            capture_output=True, text=True, timeout=RUN_TIMEOUT_S,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()[-800:]
            raise EngineError(f"acadsharp {args[0]} failed: {detail}")
        return result

    def read(self, path: Path) -> ParsedDrawing:
        with tempfile.TemporaryDirectory() as tmp:
            out_json = Path(tmp) / "out.json"
            self._run(["read", str(path), str(out_json)])
            data = json.loads(out_json.read_text())
        return ParsedDrawing(
            layers=data.get("layers", []),
            geometries=[Geometry(**g) for g in data.get("geometries", [])],
            texts=[TextItem(**t) for t in data.get("texts", [])],
        )

    def write(self, drawing: ParsedDrawing, out_path: Path, version: str = "r2018") -> Path:
        spec = {
            "layers": drawing.layers,
            "geometries": [g.model_dump() for g in drawing.geometries],
            "texts": [t.model_dump() for t in drawing.texts],
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(spec))
            self._run(["write", str(spec_path), str(out_path), version])
        return out_path

    def convert(self, src: Path, out_path: Path, version: str = "r2018") -> Path:
        """Read then re-save without going through our ParsedDrawing (keeps
        entity types the read/write mapping doesn't cover yet, e.g. HATCH -
        useful for round-trip fidelity testing on real, complex files)."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(["convert", str(src), str(out_path), version])
        return out_path
