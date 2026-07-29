"""DXF -> DWG conversion (the write-back half of `converter.py`).

Engine: LibreDWG `dxf2dwg` (same toolchain already built for `dwg2dxf`, see
DEPLOYMENT.md §3). Write support is markedly less mature than read support —
hands-on testing (see docs/CAD_MANIPULATION_ENGINE.md §3) found:
- `--as r2004` silently **drops all modelspace entities** (only layers/
  styles survive) — unusable for real content despite exiting cleanly.
- `--as r2000` writes entities correctly (independently verified via
  `dwgread`'s object-tree dump), which is why it's the default below — but
  reading that DWG back through our *own* `dwg2dxf` fails (a bug in
  dwg2dxf's DXF export, not in the DWG itself). Don't round-trip a
  dxf2dwg-written file through dwg2dxf for verification; use `dwgread` or a
  second implementation (LibreCAD, real AutoCAD) instead.

ODA File Converter (`ODA_CONVERTER_PATH`) is a higher-fidelity alternative
once real DWG round-trip fidelity is needed; wire it here the same way
`converter.py` wires it for reads.
"""
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings

WRITE_TIMEOUT_S = 60
DEFAULT_DWG_VERSION = "r2000"


class WriteError(RuntimeError):
    pass


def find_dxf2dwg() -> Path | None:
    settings = get_settings()
    if settings.dxf2dwg_path and Path(settings.dxf2dwg_path).expanduser().exists():
        return Path(settings.dxf2dwg_path).expanduser()
    found = shutil.which("dxf2dwg")
    if found:
        return Path(found)
    local = Path.home() / ".local" / "bin" / "dxf2dwg"
    return local if local.exists() else None


def dxf_to_dwg(source: Path, out_dir: Path | None = None, version: str = DEFAULT_DWG_VERSION) -> Path:
    """Convert a DXF file to a real, standalone .dwg deliverable."""
    binary = find_dxf2dwg()
    if not binary:
        raise WriteError(
            "No DXF->DWG writer available. Install LibreDWG's dxf2dwg (set DXF2DWG_PATH) "
            "or use the DXF output directly."
        )
    out_dir = out_dir or source.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{source.stem}.dwg"

    cmd = [str(binary), "-y", "--as", version, "-o", str(target), str(source)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=WRITE_TIMEOUT_S)
    if not target.exists() or target.stat().st_size == 0:
        detail = (result.stderr or result.stdout or "").strip()[-500:]
        raise WriteError(f"dxf2dwg failed for {source.name}: {detail}")
    return target
