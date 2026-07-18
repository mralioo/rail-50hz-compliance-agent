"""DXF entity extraction with ezdxf.

Reads modelspace entities into the plain `Geometry`/`TextItem` schema types so
downstream code (geometry math, agent, frontend canvas) never touches ezdxf.
"""
from pathlib import Path

import ezdxf

from app.models.schemas import Geometry, TextItem


def parse_dxf(path: Path) -> tuple[list[str], list[Geometry], list[TextItem]]:
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    layers = sorted(layer.dxf.name for layer in doc.layers)
    geometries: list[Geometry] = []
    texts: list[TextItem] = []

    for entity in msp:
        kind = entity.dxftype()
        layer = entity.dxf.layer

        if kind == "LWPOLYLINE":
            points = [(p[0], p[1]) for p in entity.get_points()]
            geometries.append(
                Geometry(layer=layer, kind="polyline", points=points, closed=entity.closed)
            )
        elif kind == "LINE":
            start, end = entity.dxf.start, entity.dxf.end
            geometries.append(
                Geometry(layer=layer, kind="line", points=[(start.x, start.y), (end.x, end.y)])
            )
        elif kind == "CIRCLE":
            center = entity.dxf.center
            geometries.append(
                Geometry(
                    layer=layer,
                    kind="circle",
                    points=[(center.x, center.y)],
                    radius=entity.dxf.radius,
                )
            )
        elif kind in ("TEXT", "MTEXT"):
            text = entity.dxf.text if kind == "TEXT" else entity.plain_text()
            insert = entity.dxf.insert
            texts.append(TextItem(layer=layer, text=text.strip(), position=(insert.x, insert.y)))

    return layers, geometries, texts
