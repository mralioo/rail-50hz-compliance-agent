"""Shared FreeCAD op logic - runs *inside* FreeCAD's Python (either the
headless one-shot `worker.py` or the persistent GUI `live_session.py`, see
docs/CRAFTSMAN_AGENT.md). Split out of what used to be all of worker.py so
both entrypoints call the identical op handlers instead of duplicating them.

Three composable pieces instead of one `run()`, because the live session
needs to hold `doc`/`layer_map`/`last_id` open across many separate op
requests instead of the one-shot path's single call-then-discard:
    open_and_prepare(dxf_path) -> (doc, layer_map)
    run_ops(doc, layer_map, ops, last_id) -> (op_results, last_id)
    extract(doc, layer_map) -> (geometries, texts, objects, warnings)
`run(job)` composes all three for the one-shot path - unchanged behavior.
"""
import FreeCAD
import Draft
import importDXF

ARC_TESSELLATION_POINTS = 8

# FreeCAD's internal document unit is always millimeters, regardless of the
# source file's own units - it rescales on import (confirmed hands-on: the
# importer logs "Final scaling: 1 DXF unit = 1000.0000 mm" for a meters-unit
# DXF). Op *inputs* (offset_wire's delta, fillet_wire's radius) are meant to
# be real millimeters and are applied as-is to that native mm space, which
# is correct. But this codebase's Geometry/TextItem convention (dxf_parser.py,
# geometry.py's "m"/"m²" metrics) is real-world units matching the source
# DXF's own $INSUNITS (meters, for every fixture and real plan in this repo) -
# so raw FreeCAD coordinates must be scaled back down by this factor before
# they're returned, or the exported geometry ends up 1000x too large (found
# hands-on: a real plan's ~140m extent came out as ~140,000 km, invisible at
# any sane viewer zoom despite every entity/layer/text being present and
# correct).
FREECAD_MM_TO_DOC_UNIT = 0.001


def _set_import_preferences():
    # Defaults for a fresh FreeCAD profile import text/joined-geometry OFF,
    # which would silently drop annotation TEXT entities and fragment
    # LWPOLYLINEs into loose Line/Arc objects - confirmed hands-on against
    # backend/data/samples/cad_engine_poc/dummy_project.dxf.
    prefs = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Draft")
    prefs.SetBool("dxftext", True)
    prefs.SetBool("joingeometry", True)
    # dxfShowDialog defaults to True and only takes effect when FreeCAD.GuiUp
    # is true (importDXF.py's `gui and ... hGrp.GetBool("dxfShowDialog",
    # True)` branch) - irrelevant for the headless worker.py path (GuiUp is
    # always False there) but fatal for live_session.py's persistent GUI
    # session: importDXF.open() pops a modal DxfImportDialog and blocks
    # forever waiting for a click that will never come (confirmed hands-on -
    # the call simply never returns, no exception, nothing in the log).
    prefs.SetBool("dxfShowDialog", False)


def _build_layer_map(doc) -> dict:
    """object name -> original DXF layer, seeded from the importer's own
    `OriginalLayer` property (present on every entity it created, absent on
    the administrative Layer/LayerContainer group objects it also creates -
    so this doubles as the "is this a real geometry/text object" filter)."""
    layer_map = {}
    for obj in doc.Objects:
        layer = getattr(obj, "OriginalLayer", None)
        if layer:
            layer_map[obj.Name] = layer
    return layer_map


def _scaled(x: float, y: float) -> list[float]:
    return [x * FREECAD_MM_TO_DOC_UNIT, y * FREECAD_MM_TO_DOC_UNIT]


def _edge_points(edge):
    """Ordered (x, y) points along one edge, in FreeCAD's native mm (caller
    scales) - exact endpoints for a straight Line, a tessellated sample for
    anything curved (Arc/Circle), since the project's Geometry schema has no
    bulge/arc representation."""
    if type(edge.Curve).__name__ == "Line":
        v0, v1 = edge.Vertexes[0], edge.Vertexes[1]
        return [(v0.X, v0.Y), (v1.X, v1.Y)]
    pts = edge.discretize(Number=ARC_TESSELLATION_POINTS)
    return [(p.x, p.y) for p in pts]


def _edges_to_geometry(edges, closed: bool, layer: str) -> dict:
    if len(edges) == 1:
        edge = edges[0]
        curve_name = type(edge.Curve).__name__
        if curve_name == "Line":
            v0, v1 = edge.Vertexes[0], edge.Vertexes[1]
            return {
                "layer": layer, "kind": "line",
                "points": [_scaled(v0.X, v0.Y), _scaled(v1.X, v1.Y)],
                "closed": False, "radius": None,
            }
        if curve_name == "Circle" and len(edge.Vertexes) == 1:
            center = edge.Curve.Center
            return {
                "layer": layer, "kind": "circle",
                "points": [_scaled(center.x, center.y)], "closed": False,
                "radius": edge.Curve.Radius * FREECAD_MM_TO_DOC_UNIT,
            }
    points: list[tuple[float, float]] = []
    for edge in edges:
        pts = _edge_points(edge)
        if points and points[-1] == pts[0]:
            pts = pts[1:]
        points.extend(pts)
    return {
        "layer": layer, "kind": "polyline",
        "points": [_scaled(*p) for p in points], "closed": closed, "radius": None,
    }


def extract(doc, layer_map: dict) -> tuple[list, list, list, list, list]:
    """Returns (geometries, texts, objects, warnings, dropped_ids). `objects`
    is a parallel id index - `{"id": <FreeCAD object name>, "kind":
    "geometry"|"text", "layer": ...}` in the same order as geometries then
    texts - so a caller can turn a snapshot (an empty-`ops` call) into the
    `id`s the next call's `offset_wire`/`fillet_wire`/`upgrade_objects` ops
    need. Geometry/TextItem (app/models/schemas.py) has no id field of its
    own - this is additive, not a change to that shared schema. `dropped_ids`
    is the FreeCAD object names behind each `warnings` entry - live_session.py
    uses it to hide those objects' ViewObjects before fitting the camera (see
    _drop_coordinate_outliers's docstring for why leaving them visible breaks
    the live view's auto-fit even though they're already excluded here)."""
    geometries: list[dict] = []
    texts: list[dict] = []
    objects: list[dict] = []
    for obj in doc.Objects:
        layer = layer_map.get(obj.Name)
        if layer is None:
            continue  # administrative (Layer/LayerContainer) or untracked object
        if Draft.get_type(obj) == "Text":
            text = " ".join(getattr(obj, "Text", []) or []).strip()
            if not text:
                continue
            base = obj.Placement.Base
            texts.append({"layer": layer, "text": text, "position": _scaled(base.x, base.y)})
            objects.append({"id": obj.Name, "kind": "text", "layer": layer})
        elif hasattr(obj, "Shape") and not obj.Shape.isNull():
            wires = obj.Shape.Wires
            if wires:
                # A closed/joined shape (e.g. an imported LWPOLYLINE, or the
                # result of upgrade_objects/offset/fillet).
                for wire in wires:
                    geometries.append(_edges_to_geometry(wire.Edges, wire.isClosed(), layer))
                    objects.append({"id": obj.Name, "kind": "geometry", "layer": layer})
            elif obj.Shape.Edges:
                # A bare single-entity import (plain LINE/CIRCLE) has no Wire
                # wrapper at all - confirmed hands-on against
                # dummy_project.dxf's cable LINE and CIRCLE objects, which
                # otherwise silently vanished from the output entirely.
                geometries.append(_edges_to_geometry(obj.Shape.Edges, False, layer))
                objects.append({"id": obj.Name, "kind": "geometry", "layer": layer})
    return _drop_coordinate_outliers(geometries, texts, objects)


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


# How many median-absolute-deviations from the plan's own center a point can
# be before it's treated as corrupt rather than just "a feature far from the
# middle of the drawing" - deliberately extreme so this never touches real
# geometry, only the multi-million-unit magnitude of the bug below.
OUTLIER_MAD_MULTIPLIER = 200


def _drop_coordinate_outliers(
    geometries: list[dict], texts: list[dict], objects: list[dict]
) -> tuple[list[dict], list[dict], list[dict], list[str], list[str]]:
    """Defensive guard against a FreeCAD DXF-importer bug found hands-on
    against a real DB plan: a DXF SOLID entity (a filled road-marking shape)
    came back with its Shape.BoundBox mirrored across X - millions of units
    from every other entity in the same drawing, purely from FreeCAD's own
    import, before this worker's extraction even runs. One such point is
    enough to blow up any "fit everything" viewer's auto-zoom, making the
    entire real plan invisible even though every other entity is correct.
    Median (not mean/min/max) + MAD (not stddev) because both are robust to
    a small number of extreme outliers - a plain bounding-box check would be
    dominated by the very corruption it's trying to detect. See
    docs/CRAFTSMAN_AGENT.md."""
    if len(geometries) < 4:  # too few points for a meaningful median/MAD
        return geometries, texts, objects, [], []

    all_x = [p[0] for g in geometries for p in g["points"]]
    all_y = [p[1] for g in geometries for p in g["points"]]
    mx, my = _median(all_x), _median(all_y)
    mad_x = max(_median([abs(x - mx) for x in all_x]), 1e-6)
    mad_y = max(_median([abs(y - my) for y in all_y]), 1e-6)
    limit_x = mad_x * OUTLIER_MAD_MULTIPLIER
    limit_y = mad_y * OUTLIER_MAD_MULTIPLIER

    def is_outlier(points: list[list[float]]) -> bool:
        return any(abs(p[0] - mx) > limit_x or abs(p[1] - my) > limit_y for p in points)

    warnings: list[str] = []
    dropped_ids: list[str] = []
    clean_geometries, clean_geom_objects = [], []
    for geo, obj in zip(geometries, objects[: len(geometries)]):
        if is_outlier(geo["points"]):
            warnings.append(
                f"dropped a {geo['kind']} (id={obj['id']!r}, layer={geo['layer']!r}) - "
                "coordinates far outside the plan's extent (FreeCAD DXF import artifact, "
                "see docs/CRAFTSMAN_AGENT.md)"
            )
            dropped_ids.append(obj["id"])
            continue
        clean_geometries.append(geo)
        clean_geom_objects.append(obj)

    clean_texts, clean_text_objects = [], []
    for txt, obj in zip(texts, objects[len(geometries):]):
        if is_outlier([txt["position"]]):
            warnings.append(
                f"dropped text (id={obj['id']!r}, layer={txt['layer']!r}) - position far "
                "outside the plan's extent (FreeCAD DXF import artifact)"
            )
            dropped_ids.append(obj["id"])
            continue
        clean_texts.append(txt)
        clean_text_objects.append(obj)

    return clean_geometries, clean_texts, clean_geom_objects + clean_text_objects, warnings, dropped_ids


class OpError(ValueError):
    pass


# Sentinel an op's id/ids can use instead of a real FreeCAD object name,
# meaning "whatever the previous op in this same job's ops list just
# created". Exists because each POST /craftsman call re-reads the original
# upload from scratch (app/api/routes.py's craftsman_manipulate docstring;
# see docs/CRAFTSMAN_AGENT.md) - a multi-step SOP that spans several
# *separate* calls therefore can't reference an earlier call's output id at
# all (it no longer exists once that call's FreeCAD doc is discarded) -
# except the live session (live_session.py), where the doc stays open across
# calls and $prev naturally persists for the whole session, not just one
# call. Within a *single* call, ops run against the same in-memory `doc` in
# order, so chaining is real and correct here - the caller just can't know
# the exact FreeCAD-assigned name (e.g. upgrading a closed wire yields
# "Face", an open one yields "Wire") without running it first. $prev removes
# that guesswork: build the whole multi-op SOP client-side with $prev
# between steps instead of predicting names. Found necessary hands-on: a
# client that diffed object-id lists between separate calls to "chain"
# steps failed with `unknown object id` because the id from call N simply
# isn't there in call N+1's fresh document.
PREV_ID = "$prev"


def _resolve_id(raw_id: str | None, last_id: str | None) -> str:
    if raw_id == PREV_ID:
        if last_id is None:
            raise OpError(f"{PREV_ID!r} used but no prior op in this call created an object")
        return last_id
    return raw_id or ""


def _op_upgrade_objects(doc, layer_map: dict, args: dict, last_id: str | None) -> tuple[str, str | None]:
    ids = [_resolve_id(i, last_id) for i in (args.get("ids") or [])]
    objs = [doc.getObject(i) for i in ids]
    if not all(objs):
        raise OpError(f"unknown object id in {ids}")
    source_layer = layer_map.get(objs[0].Name, "0")
    new_objs, _deleted = Draft.upgrade(objs, delete=True)
    doc.recompute()
    for obj in new_objs:
        layer_map[obj.Name] = source_layer
    new_names = [o.Name for o in new_objs]
    return f"upgraded {ids} -> {new_names}", (new_names[-1] if new_names else None)


def _op_offset_wire(doc, layer_map: dict, args: dict, last_id: str | None) -> tuple[str, str | None]:
    target_id = _resolve_id(args.get("id"), last_id)
    obj = doc.getObject(target_id)
    if obj is None:
        raise OpError(f"unknown object id {target_id!r}")
    dx, dy, dz = (list(args.get("delta") or [0, 0, 0]) + [0, 0, 0])[:3]
    source_layer = layer_map.get(obj.Name, "0")
    new_obj = Draft.offset(obj, FreeCAD.Vector(dx, dy, dz), copy=True)
    if new_obj is None:
        raise OpError(f"offset failed for {obj.Name}")
    doc.recompute()
    layer_map[new_obj.Name] = source_layer
    return f"offset {obj.Name} by ({dx}, {dy}, {dz}) -> {new_obj.Name}", new_obj.Name


def _op_fillet_wire(doc, layer_map: dict, args: dict, last_id: str | None) -> tuple[str, str | None]:
    target_id = _resolve_id(args.get("id"), last_id)
    obj = doc.getObject(target_id)
    if obj is None:
        raise OpError(f"unknown object id {target_id!r}")
    indices = args.get("edge_indices") or []
    if len(indices) != 2:
        raise OpError("fillet_wire requires exactly 2 edge_indices")
    try:
        edges = [obj.Shape.Edges[i] for i in indices]
    except IndexError:
        raise OpError(f"edge_indices {indices} out of range for {obj.Name}") from None
    radius = float(args.get("radius", 100))
    source_layer = layer_map.get(obj.Name, "0")
    new_obj = Draft.make_fillet(edges, radius=radius)
    if new_obj is None:
        raise OpError(f"fillet failed for {obj.Name} edges {indices} (are they adjacent?)")
    doc.recompute()
    layer_map[new_obj.Name] = source_layer
    return f"filleted {obj.Name} edges {indices} r={radius} -> {new_obj.Name}", new_obj.Name


OPS = {
    "upgrade_objects": _op_upgrade_objects,
    "offset_wire": _op_offset_wire,
    "fillet_wire": _op_fillet_wire,
}


def open_and_prepare(dxf_path: str):
    """Opens `dxf_path` as a fresh FreeCAD document, ready for run_ops/
    extract. Raises OpError if FreeCAD can't open it."""
    _set_import_preferences()
    doc = importDXF.open(dxf_path)
    if doc is None:
        raise OpError(f"FreeCAD could not open {dxf_path!r}")
    layer_map = _build_layer_map(doc)
    return doc, layer_map


def run_ops(doc, layer_map: dict, ops: list[dict], last_id: str | None) -> tuple[list[dict], str | None]:
    """Runs `ops` against the already-open `doc` in order, chaining $prev
    via `last_id` exactly as a single one-shot call does - but callable
    repeatedly against the same doc (the live session's whole point), with
    `last_id` threaded in and back out so it survives across calls too."""
    op_results = []
    for op in ops:
        name = op.get("op")
        handler = OPS.get(name)
        if handler is None:
            op_results.append({"op": name, "ok": False, "detail": f"unknown op {name!r}"})
            continue
        try:
            detail, new_id = handler(doc, layer_map, op, last_id)
            op_results.append({"op": name, "ok": True, "detail": detail})
            if new_id:
                last_id = new_id
        except Exception as exc:  # a bad op shouldn't lose the rest of the job
            op_results.append({"op": name, "ok": False, "detail": str(exc)})
    return op_results, last_id


def run(job: dict) -> dict:
    """One-shot convenience wrapper composing open_and_prepare/run_ops/
    extract - what worker.py's headless CLI path calls. The live session
    (live_session.py) calls the three pieces directly instead, since it
    needs to hold `doc`/`layer_map`/`last_id` open across many separate
    calls rather than one call-then-discard."""
    doc, layer_map = open_and_prepare(job["input"])
    op_results, _last_id = run_ops(doc, layer_map, job.get("ops", []), None)
    geometries, texts, objects, warnings, _dropped_ids = extract(doc, layer_map)
    return {
        "ok": True,
        "error": None,
        "op_results": op_results,
        "layers": sorted(set(layer_map.values())),
        "geometries": geometries,
        "texts": texts,
        "objects": objects,
        "warnings": warnings,
    }
