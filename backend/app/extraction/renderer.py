"""Server-side plan rendering via ezdxf's drawing add-on (matplotlib Agg).

Unlike the entity parser, the drawing frontend resolves block references
(INSERT), hatches and dimensions — the render shows everything the data
layer doesn't extract yet (~1.8 s for a real 907 KB DXF).

Alongside the PNG a `<name>.json` metadata file records the world-coordinate
window and pixel size of the image, so the locator agent can map plan
coordinates onto image positions for UI overlays.
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — must precede pyplot import

import ezdxf
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

BACKGROUND = "#14181D"  # matches the Flutter canvas background


def render_png(
    dxf_path: Path,
    out_path: Path,
    max_px: int = 2600,
    layers: set[str] | None = None,
    world: tuple[float, float, float, float] | None = None,
) -> Path:
    """Render modelspace to PNG.

    `layers`: render only these layer names (None = all).
    `world`: force this world window (x0, y0, x1, y1) — used for filtered
    variants so they stay pixel-aligned with the base render and its overlays.
    """
    doc = ezdxf.readfile(str(dxf_path))
    if layers is not None:
        for layer in doc.layers:
            if layer.dxf.name not in layers:
                layer.off()
    fig = plt.figure()
    try:
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor(BACKGROUND)
        Frontend(RenderContext(doc), MatplotlibBackend(ax)).draw_layout(
            doc.modelspace(), finalize=True
        )
        if world is not None:
            ax.set_xlim(world[0], world[2])
            ax.set_ylim(world[1], world[3])
        # finalize() re-fits the figure to the drawing's aspect ratio, so the
        # output dpi must be derived from the FINAL size to hit max_px
        fig_w, fig_h = fig.get_size_inches()
        dpi = max_px / max(fig_w, fig_h)
        fig.savefig(out_path, facecolor=BACKGROUND, dpi=dpi)

        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        out_path.with_suffix(".json").write_text(json.dumps({
            "world": [x0, y0, x1, y1],  # displayed window incl. padding
            "px": [round(fig_w * dpi), round(fig_h * dpi)],
            "dxf": str(dxf_path),  # enables on-demand filtered re-renders
        }))
    finally:
        plt.close(fig)
    return out_path


def load_render_meta(png_path: Path) -> dict | None:
    meta_path = png_path.with_suffix(".json")
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text())
