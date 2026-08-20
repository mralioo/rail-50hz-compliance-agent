"""Bakes agent output (locator hits, draftsman sketches) into a copy of a
job's DXF as real, highlighted entities on dedicated layers - so the
cad-viewer export shows agent output as interactive geometry (pan/zoom/
select it) instead of a raster overlay image.

Kept separate from app.domain.cad/app.adapters.cad: that framework is for
engine-agnostic read/write round-trips (ParsedDrawing <-> DWG/DXF); this
only ever feeds app.viewer.cad_viewer_export.export_html, so it uses ezdxf
directly for per-layer color control (ACI colors), which
ParsedDrawing/CadEnginePort.write() doesn't expose today.
"""
from pathlib import Path

import ezdxf

from app.models.schemas import DrawnElement, LocateHit

LOCATOR_HIT_LAYER = "AGENT_LOCATOR_HIT"
LOCATOR_HIT_COLOR = 2  # ACI yellow

DRAFT_LAYER = "AGENT_DRAFT"
DRAFT_COLOR = 1  # ACI red


def build_annotated_dxf(
    base_dxf_path: Path,
    out_path: Path,
    *,
    locate_hits: list[LocateHit] = (),
    drawn_elements: list[DrawnElement] = (),
) -> Path:
    doc = ezdxf.readfile(str(base_dxf_path))
    msp = doc.modelspace()

    if locate_hits:
        if LOCATOR_HIT_LAYER not in doc.layers:
            doc.layers.add(LOCATOR_HIT_LAYER, color=LOCATOR_HIT_COLOR)
        for hit in locate_hits:
            x0, y0, x1, y1 = hit.world_bbox
            attribs = {"layer": LOCATOR_HIT_LAYER}
            if hit.color:
                # Per-entity true_color overrides the layer's ACI color for
                # just this hit, so a single locate call can mix colors
                # (e.g. re-highlighting one earlier hit differently) without
                # needing a new layer per color.
                attribs["true_color"] = int(hit.color.lstrip("#"), 16)
            msp.add_lwpolyline(
                [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                close=True,
                dxfattribs=attribs,
            )

    if drawn_elements:
        if DRAFT_LAYER not in doc.layers:
            doc.layers.add(DRAFT_LAYER, color=DRAFT_COLOR)
        for element in drawn_elements:
            msp.add_lwpolyline(element.points_world, dxfattribs={"layer": DRAFT_LAYER})
            if element.label:
                msp.add_text(
                    element.label, dxfattribs={"layer": DRAFT_LAYER, "height": 0.2}
                ).set_placement(element.points_world[0])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)
    return out_path
