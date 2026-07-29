"""Adapter for `@mlightcad/cad-html-exporter-cli` - converts a DXF into a
self-contained, interactive offline HTML viewer (Three.js/WebGL: pan/zoom/
measure/layers). See docs/CAD_VIEWER_INTEGRATION.md.

DXF only, by design. The library's default DWG parsing path depends on
GPL-3.0 `libredwg-web`/`libredwg-converter` - unlike our backend's
subprocess-only use of LibreDWG elsewhere, that code would ship as part of
the exported HTML artifact (verified: an HTML exported from a DXF input has
zero occurrences of "libredwg" in it - the GPL parser is only pulled in for
.dwg input). Our pipeline already produces a canonical DXF for every job
(`app.ingestion.converter.ensure_dxf`), so this adapter never receives a
.dwg and the exported HTML stays MIT-clean.

Normalizes the input through ezdxf before export. A real-world DXF that
ezdxf's own reader accepts outright (`Kreuzungsplan.dxf`, 956KB/1260
entities) still failed cad-viewer's importer in testing
(`Error: Failed to open "..."`); a plain ezdxf read+resave - with zero
entities changed - fixed it every time. Root cause not pinned down (some
structural quirk ezdxf's writer normalizes away that cad-viewer's parser
doesn't tolerate), but the fix is cheap - well under a second, against a
~3s+ Chromium export - so it's applied unconditionally rather than treated
as an edge case.

Also recenters the geometry when it sits far from the origin (real-world
survey coordinate systems - Gauss-Kruger/UTM - routinely put drawings at
absolute coordinates in the millions). cad-viewer's renderer (bundled
Three.js) uploads vertex positions as `Float32Array`; float32 has ~7
significant decimal digits, so a coordinate like 3,570,517.934 only carries
~0.4 units of precision - larger than this ~140-unit-wide plan's entire
extent. The geometry parses and its layers/metadata are all correct (proven
by the layer panel listing everything normally), but every vertex collapses
toward the same handful of quantized float32 values on the GPU, so nothing
visible survives: a fully blank canvas, no error, camera and toolbar both
functional. Confirmed by re-exporting the same file with entities
translated near the origin - the drawing rendered correctly immediately.
Threshold-gated (`RECENTER_THRESHOLD_UNITS`) rather than unconditional, so
already-origin-centered drawings (the common case) are byte-for-byte
unaffected - this changes the exported HTML's coordinate frame, which
matters if a user reads absolute survey coordinates off the measure tool.
"""
import subprocess
import shutil
import tempfile
from pathlib import Path

import ezdxf.bbox
import ezdxf.recover

from app.core.config import get_settings

RUN_TIMEOUT_S = 90
CLI_RELATIVE_PATH = Path(
    "tools/cad_viewer_cli/node_modules/@mlightcad/cad-html-exporter-cli/dist/cli.js"
)

# Above this distance (drawing units) from the origin, cad-viewer's Three.js
# renderer loses enough float32 precision to render the geometry as blank -
# see module docstring. Real survey coordinate systems sit in the millions;
# ordinary drawings are near (0, 0), so this threshold cleanly separates the
# two cases without touching normal files.
RECENTER_THRESHOLD_UNITS = 100_000.0


class CadViewerError(RuntimeError):
    """Raised when the cad-html-exporter subprocess is unavailable or fails."""


def find_node() -> Path | None:
    settings = get_settings()
    if settings.node_path and Path(settings.node_path).expanduser().exists():
        return Path(settings.node_path).expanduser()
    found = shutil.which("node")
    if found:
        return Path(found)
    local = Path.home() / "nodejs" / "bin" / "node"
    return local if local.exists() else None


def find_exporter_cli() -> Path | None:
    settings = get_settings()
    if settings.cad_viewer_cli_path and Path(settings.cad_viewer_cli_path).expanduser().exists():
        return Path(settings.cad_viewer_cli_path).expanduser()
    from app.core.config import BACKEND_ROOT
    candidate = BACKEND_ROOT / CLI_RELATIVE_PATH
    return candidate if candidate.exists() else None


def _recenter_if_far(doc: "ezdxf.document.Drawing") -> None:
    """Translate modelspace entities toward the origin if the drawing sits
    far enough away that cad-viewer's float32 vertex buffers would collapse
    it to nothing (see module docstring). Applied last, after any locator-
    hit / draftsman annotations have already been baked in on the same
    coordinate frame (`app.viewer.annotate`), so the whole document -
    original geometry and annotations alike - is translated together and
    stays aligned.
    """
    msp = doc.modelspace()
    bbox = ezdxf.bbox.extents(msp, fast=True)
    if not bbox.has_data:
        return
    cx, cy, cz = bbox.center
    if max(abs(cx), abs(cy)) < RECENTER_THRESHOLD_UNITS:
        return
    for entity in list(msp):
        try:
            entity.translate(-cx, -cy, -cz)
        except Exception:
            pass  # not every entity type implements the transform interface; leave it in place rather than fail the whole export
    new_bbox = ezdxf.bbox.extents(msp, fast=True)
    if new_bbox.has_data:
        doc.header["$EXTMIN"] = tuple(new_bbox.extmin)
        doc.header["$EXTMAX"] = tuple(new_bbox.extmax)


def _normalize_dxf(dxf_path: Path, tmp_dir: Path) -> Path:
    doc, _auditor = ezdxf.recover.readfile(str(dxf_path))
    _recenter_if_far(doc)
    normalized = tmp_dir / f"normalized_{dxf_path.name}"
    doc.saveas(normalized)
    return normalized


def export_html(
    dxf_path: Path,
    out_path: Path,
    *,
    title: str | None = None,
    locale: str = "en",
    viewer_mode: str = "measure",
    initial_view: str = "fit",
) -> Path:
    node = find_node()
    cli = find_exporter_cli()
    if not node or not cli:
        raise CadViewerError(
            "cad-html-exporter not available. Set up tools/cad_viewer_cli (see "
            "docs/CAD_VIEWER_INTEGRATION.md): cd tools/cad_viewer_cli && npm install "
            "&& npx playwright install chromium. Set NODE_PATH/CAD_VIEWER_CLI_PATH "
            "if not auto-detected."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        normalized = _normalize_dxf(dxf_path, Path(tmp))
        args = [
            str(node), str(cli), str(normalized),
            "-o", str(out_path),
            "--locale", locale,
            "--viewer-mode", viewer_mode,
            "--initial-view", initial_view,
        ]
        if title:
            args += ["--title", title]
        result = subprocess.run(args, capture_output=True, text=True, timeout=RUN_TIMEOUT_S)
        if result.returncode != 0 or not out_path.exists():
            detail = (result.stderr or result.stdout or "").strip()[-800:]
            raise CadViewerError(f"cad-html-exporter failed: {detail}")
    return out_path
