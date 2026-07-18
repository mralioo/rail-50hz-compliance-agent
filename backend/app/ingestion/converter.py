"""DWG -> DXF conversion.

Two interchangeable engines, picked automatically:
- LibreDWG `dwg2dxf` (open source; built from source on this machine) —
  preferred when `DWG2DXF_PATH` is set or the binary is on PATH.
- ODA File Converter — optional, higher fidelity, via `ODA_CONVERTER_PATH`.

DXF uploads are passed through untouched, so the pipeline works with neither
engine installed.
"""
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings

ODA_OUTPUT_VERSION = "ACAD2018"
CONVERT_TIMEOUT_S = 120


class ConversionError(RuntimeError):
    pass


def ensure_dxf(source: Path, out_dir: Path | None = None) -> Path:
    suffix = source.suffix.lower()
    if suffix == ".dxf":
        return source
    if suffix == ".dwg":
        return convert_dwg(source, out_dir)
    raise ConversionError(f"Unsupported file type: {suffix} (expected .dwg or .dxf)")


def find_dwg2dxf() -> Path | None:
    settings = get_settings()
    if settings.dwg2dxf_path and Path(settings.dwg2dxf_path).expanduser().exists():
        return Path(settings.dwg2dxf_path).expanduser()
    found = shutil.which("dwg2dxf")
    if found:
        return Path(found)
    local = Path.home() / ".local" / "bin" / "dwg2dxf"
    return local if local.exists() else None


def convert_dwg(source: Path, out_dir: Path | None = None) -> Path:
    out_dir = out_dir or source.parent / "converted"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{source.stem}.dxf"

    if dwg2dxf := find_dwg2dxf():
        return _run_dwg2dxf(dwg2dxf, source, target)
    if get_settings().oda_converter_path:
        return _run_oda(source, out_dir)
    raise ConversionError(
        "No DWG converter available. Install LibreDWG's dwg2dxf (set DWG2DXF_PATH) "
        "or the ODA File Converter (set ODA_CONVERTER_PATH), or upload a .dxf file."
    )


def _run_dwg2dxf(binary: Path, source: Path, target: Path) -> Path:
    cmd = [str(binary), "-y", "-o", str(target), str(source)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=CONVERT_TIMEOUT_S)
    # dwg2dxf can exit non-zero on recoverable warnings; trust the output file
    if not target.exists() or target.stat().st_size == 0:
        detail = (result.stderr or result.stdout or "").strip()[-500:]
        raise ConversionError(f"dwg2dxf failed for {source.name}: {detail}")
    return target


def _run_oda(source: Path, out_dir: Path) -> Path:
    settings = get_settings()
    # ODAFileConverter <in_dir> <out_dir> <version> <type> <recurse> <audit> [filter]
    cmd = [
        str(settings.oda_converter_path),
        str(source.parent),
        str(out_dir),
        ODA_OUTPUT_VERSION,
        "DXF",
        "0",
        "1",
        source.name,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=CONVERT_TIMEOUT_S)
    converted = out_dir / f"{source.stem}.dxf"
    if result.returncode != 0 or not converted.exists():
        raise ConversionError(f"ODA conversion failed: {result.stderr or result.stdout}")
    return converted
