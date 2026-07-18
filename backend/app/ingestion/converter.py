"""DWG -> DXF conversion via the ODA File Converter CLI.

DXF uploads are passed through untouched, so the whole pipeline works without
ODA installed — only raw .dwg files need the binary (set ODA_CONVERTER_PATH).
"""
import subprocess
from pathlib import Path

from app.core.config import get_settings

ODA_OUTPUT_VERSION = "ACAD2018"


class ConversionError(RuntimeError):
    pass


def ensure_dxf(source: Path) -> Path:
    suffix = source.suffix.lower()
    if suffix == ".dxf":
        return source
    if suffix == ".dwg":
        return _convert_dwg(source)
    raise ConversionError(f"Unsupported file type: {suffix} (expected .dwg or .dxf)")


def _convert_dwg(source: Path) -> Path:
    settings = get_settings()
    if not settings.oda_converter_path:
        raise ConversionError(
            "DWG upload requires the ODA File Converter. "
            "Set ODA_CONVERTER_PATH in backend/.env, or upload a .dxf file instead."
        )

    out_dir = source.parent / "converted"
    out_dir.mkdir(exist_ok=True)

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
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    converted = out_dir / f"{source.stem}.dxf"
    if result.returncode != 0 or not converted.exists():
        raise ConversionError(f"ODA conversion failed: {result.stderr or result.stdout}")
    return converted
