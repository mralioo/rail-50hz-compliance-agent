"""ezdxf adapter - DXF only, no DWG (ezdxf never touches DWG by design).

Read side reuses `app.extraction.dxf_parser.parse_dxf` directly rather than
duplicating its `ezdxf.recover.readfile` logic - one source of truth for
"how we read a DXF" whether it's the production pipeline or this benchmark
harness calling it.
"""
from pathlib import Path

import ezdxf

from app.domain.cad.ports import CadEnginePort, EngineError, ParsedDrawing
from app.extraction.dxf_parser import parse_dxf
from app.models.schemas import Geometry, TextItem

VERSION_MAP = {
    "r2000": "R2000",
    "r2004": "R2004",
    "r2007": "R2007",
    "r2010": "R2010",
    "r2013": "R2013",
    "r2018": "R2018",
}


class EzdxfEngine(CadEnginePort):
    name = "ezdxf"
    open_source = True
    reads_dxf = True
    writes_dxf = True

    def read(self, path: Path) -> ParsedDrawing:
        layers, geometries, texts = parse_dxf(path)
        return ParsedDrawing(layers=layers, geometries=geometries, texts=texts)

    def write(self, drawing: ParsedDrawing, out_path: Path, version: str = "r2018") -> Path:
        dxf_version = VERSION_MAP.get(version)
        if not dxf_version:
            raise EngineError(f"ezdxf: unknown version '{version}', expected one of {list(VERSION_MAP)}")

        doc = ezdxf.new(dxf_version)
        for name in drawing.layers:
            if name not in doc.layers:
                doc.layers.add(name)
        msp = doc.modelspace()

        for geo in drawing.geometries:
            _add_geometry(msp, geo)
        for text in drawing.texts:
            msp.add_text(text.text, dxfattribs={"layer": text.layer, "height": 0.2}).set_placement(text.position)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        doc.saveas(out_path)
        return out_path


def _add_geometry(msp, geo: Geometry) -> None:
    attribs = {"layer": geo.layer}
    if geo.kind == "polyline":
        msp.add_lwpolyline(geo.points, close=geo.closed, dxfattribs=attribs)
    elif geo.kind == "line":
        msp.add_line(geo.points[0], geo.points[1], dxfattribs=attribs)
    elif geo.kind == "circle":
        msp.add_circle(geo.points[0], radius=geo.radius or 0.1, dxfattribs=attribs)
    else:
        raise EngineError(f"ezdxf: unsupported geometry kind '{geo.kind}'")
