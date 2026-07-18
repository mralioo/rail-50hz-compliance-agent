"""Spatial math on extracted entities (shapely) + annotation mining.

Produces the metrics the compliance agent reasons over: room areas, cable run
lengths, and electrical parameters (bending radius, pulling force) parsed from
plan annotations.
"""
import re

from shapely.geometry import LineString, Polygon

from app.models.schemas import Geometry, Metric, TextItem

BEND_RADIUS_RE = re.compile(r"R\s*=?\s*(\d+(?:\.\d+)?)\s*mm", re.IGNORECASE)
PULL_FORCE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*N\b")


def compute_metrics(geometries: list[Geometry], texts: list[TextItem]) -> list[Metric]:
    metrics: list[Metric] = []

    for geo in geometries:
        if geo.kind == "polyline" and geo.closed and len(geo.points) >= 3:
            area = Polygon(geo.points).area
            metrics.append(
                Metric(name="room_area", value=round(area, 3), unit="m²", layer=geo.layer)
            )
        elif geo.kind in ("polyline", "line") and len(geo.points) >= 2:
            length = LineString(geo.points).length
            metrics.append(
                Metric(name="run_length", value=round(length, 3), unit="m", layer=geo.layer)
            )

    for item in texts:
        if match := BEND_RADIUS_RE.search(item.text):
            metrics.append(
                Metric(
                    name="cable_bending_radius",
                    value=float(match.group(1)),
                    unit="mm",
                    layer=item.layer,
                )
            )
        if (match := PULL_FORCE_RE.search(item.text)) and "pull" in item.text.lower():
            metrics.append(
                Metric(
                    name="cable_pulling_force",
                    value=float(match.group(1)),
                    unit="N",
                    layer=item.layer,
                )
            )

    return metrics


def compute_bounds(geometries: list[Geometry]) -> tuple[float, float, float, float] | None:
    points = [p for geo in geometries for p in geo.points]
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))
