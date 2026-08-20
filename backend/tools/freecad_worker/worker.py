"""Craftsman's FreeCAD worker - runs *inside* FreeCAD's Python via:

    CRAFTSMAN_JOB_PATH=<job.json> CRAFTSMAN_RESULT_PATH=<result.json> \
        FreeCADCmd worker.py

Paths travel through environment variables, not argv: FreeCADCmd treats
*every* positional argument after the script as a document to open via its
own extension dispatch (confirmed hands-on - a `.json` argument gets handed
to the Fem workbench's YAML/JSON mesh importer and crashes the process
before the script's own `sys.argv` handling ever matters), so passing the
job/result paths as CLI args is not reliable.

This is the thin, one-shot CLI entrypoint only - every op handler and the
extraction/scaling logic live in ops.py (shared with the persistent live
GUI session, live_session.py, see docs/CRAFTSMAN_AGENT.md), so both paths
run identical FreeCAD logic instead of two copies that could drift.

Job contract (written by app/craftsman/freecad_bridge.py):
    {"input": "/abs/in.dxf",
     "ops": [{"op": "upgrade_objects", "ids": ["Wire001"]},
             {"op": "offset_wire", "id": "Wire001", "delta": [150.0, 0, 0]},
             {"op": "fillet_wire", "id": "Wire003", "radius": 50.0,
              "edge_indices": [0, 1]}]}

Result contract (written to result.json - always, even on a fatal error, so
the bridge never has to guess from a bare exit code):
    {"ok": true, "error": null,
     "op_results": [{"op": "...", "ok": true, "detail": "..."}],
     "layers": ["E_ROOM", ...],
     "geometries": [{"layer": "...", "kind": "line"|"polyline"|"circle",
                      "points": [[x, y], ...], "closed": false,
                      "radius": null}],
     "texts": [{"layer": "...", "text": "...", "position": [x, y]}],
     "objects": [{"id": "Polyline", "kind": "geometry"|"text", "layer": "..."}],
     "warnings": ["dropped a polyline (id='...', layer='...') - ..."]}

`objects` is a parallel id index (same order as geometries then texts) so a
caller can discover which `id` to pass into `offset_wire`/`fillet_wire`/
`upgrade_objects` - call once with an empty `ops` list to get a snapshot,
then a second time with real ops against the `id`s it returned.

Why this doesn't call `importDXF.export()` for the output: hands-on testing
(see docs/CRAFTSMAN_AGENT.md) found the default DXF exporter in this FreeCAD
build delegates to a C++ exporter that writes every object's *name* as its
DXF layer (ignoring `OriginalLayer`) and drops Draft Text objects entirely -
exactly the two things a compliance pipeline can't afford to lose (layers
carry the E_CABLE/E_ROOM/... semantics, text carries the bend-radius/pull-
force annotations `dxf_parser.py`'s regexes depend on). Geometry and text are
extracted directly from FreeCAD's Shape/property data instead, straight into
this project's own `Geometry`/`TextItem` shape
(`app/models/schemas.py`) - the same currency `cad_engines` already uses -
so the bridge can hand the result straight to `AcadSharpEngine.write()`
without going through DXF again at all.
"""
import json
import os

import ops


def main() -> None:
    job_path = os.environ["CRAFTSMAN_JOB_PATH"]
    result_path = os.environ["CRAFTSMAN_RESULT_PATH"]
    with open(job_path) as f:
        job = json.load(f)
    try:
        result = ops.run(job)
    except Exception as exc:
        result = {
            "ok": False, "error": str(exc),
            "op_results": [], "layers": [], "geometries": [], "texts": [], "objects": [],
            "warnings": [],
        }
    with open(result_path, "w") as f:
        json.dump(result, f)


# FreeCADCmd imports this file as a module named after its filename (not
# "__main__" - confirmed hands-on), so an `if __name__ == "__main__"` guard
# never fires here; call unconditionally, same convention FreeCAD macros use.
main()
