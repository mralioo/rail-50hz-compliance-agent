"""Apply DwgEditOp edits to a ParsedDrawing in place.

Separate from the API layer (app/api/routes.py) so it's testable without
FastAPI, and separate from the engine adapters since it operates on the
engine-agnostic ParsedDrawing (app/cad_engines/base.py), not any one
engine's I/O.
"""
from app.cad_engines.base import ParsedDrawing
from app.models.schemas import DwgEditOp


class EditError(ValueError):
    """Raised for a malformed or out-of-range edit op."""


def apply_edits(drawing: ParsedDrawing, edits: list[DwgEditOp]) -> ParsedDrawing:
    for edit in edits:
        if edit.op == "add_geometry":
            if edit.geometry is None:
                raise EditError("add_geometry requires 'geometry'")
            if edit.geometry.layer not in drawing.layers:
                drawing.layers.append(edit.geometry.layer)
            drawing.geometries.append(edit.geometry)
        elif edit.op == "add_text":
            if edit.text is None:
                raise EditError("add_text requires 'text'")
            if edit.text.layer not in drawing.layers:
                drawing.layers.append(edit.text.layer)
            drawing.texts.append(edit.text)
        elif edit.op == "remove_geometry":
            if edit.index is None or not (0 <= edit.index < len(drawing.geometries)):
                raise EditError(f"remove_geometry: invalid index {edit.index}")
            del drawing.geometries[edit.index]
        elif edit.op == "remove_text":
            if edit.index is None or not (0 <= edit.index < len(drawing.texts)):
                raise EditError(f"remove_text: invalid index {edit.index}")
            del drawing.texts[edit.index]
        else:
            raise EditError(f"unknown op: {edit.op!r}")
    return drawing
