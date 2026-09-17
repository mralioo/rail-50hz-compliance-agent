"""Craftsman's live FreeCAD session - runs *inside* the real, visible FreeCAD
GUI (not FreeCADCmd) via:

    CRAFTSMAN_LIVE_INPUT=<dxf path> CRAFTSMAN_LIVE_PORT=<port> \
        FreeCAD live_session.py

launched under xpra so the GUI itself streams into the browser (xpra's
HTML5 client, see backend/app/craftsman/live_bridge.py and
docs/CRAFTSMAN_AGENT.md). Unlike worker.py's one-shot subprocess (a fresh
FreeCAD process + fresh document per call, discarded after), this process
stays alive for the whole live session: one document, opened once, that
every op request mutates in place - so an engineer watching the xpra window
sees each op redraw live, and `$prev` (ops.PREV_ID) naturally persists
across every op request instead of only within one call.

Thread-safety: FreeCAD's document/Gui objects are only safe to touch from
Qt's main thread (the same thread running the GUI event loop this script's
own top level executes on, since FreeCAD loads it as a startup script - the
same convention worker.py already uses for FreeCADCmd, confirmed hands-on
against the GUI binary too, see docs/CRAFTSMAN_AGENT.md). So:
  - a background `threading.Thread` runs a blocking accept() loop that ONLY
    reads bytes off the wire and pushes (conn, ops) onto a queue.Queue() -
    it never touches `doc`/Draft/Gui objects.
  - a QTimer created here on the main thread polls that queue and is the
    ONLY place that calls ops.run_ops/ops.extract/recompute/ViewFit - safe
    because QTimer callbacks always run on the thread that created them.
"""
import json
import os
import queue
import socket
import threading

import FreeCAD
import FreeCADGui
from PySide6 import QtCore

import ops

POLL_INTERVAL_MS = 100
REQUEST_QUEUE: "queue.Queue[tuple[socket.socket, dict]]" = queue.Queue()


def _accept_loop(port: int) -> None:
    """Background thread - reads one JSON request per connection (client
    writes then shuts down its write side; we read until EOF) and enqueues
    it. Never touches FreeCAD state directly - see module docstring."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(8)
    while True:
        conn, _addr = srv.accept()
        try:
            chunks = []
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            request = json.loads(b"".join(chunks).decode("utf-8"))
        except Exception as exc:
            try:
                conn.sendall(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8"))
            finally:
                conn.close()
            continue
        REQUEST_QUEUE.put((conn, request))


def _hide_boundbox_outliers(doc, layer_map: dict) -> None:
    """Hides ViewObjects whose raw Shape.BoundBox center sits far outside
    the plan's real extent - the same class of FreeCAD DXF-import
    corruption ops._drop_coordinate_outliers guards against for the API
    response (a mirrored SOLID entity, see docs/CRAFTSMAN_AGENT.md finding
    8), but computed directly from each object's own BoundBox instead of
    going through the geometry-extraction pipeline first. Confirmed
    hands-on that the two don't always agree: this session's actual
    corrupt object (a Face with a real Wire/Edges, layer
    VG-BLO-Fahrbahnmarkierung, BoundBox mirrored ~7.1e6m from every other
    entity) was NOT the one ops.extract's point-cloud-based median/MAD
    flagged - some other, legitimately-positioned object was flagged
    instead. `fitAll()` uses each object's BoundBox directly, so that's
    what this hides against too, independent of whatever the API-response
    filter separately decides to drop.

    Restricted to `layer_map` (objects with a real `OriginalLayer`) - a
    first version that scanned every `doc.Objects` entry hid ~25% of a real
    plan (418 of 1681 objects): DXF block *definitions* (`_BlockDefinitions`/
    `_UnreferencedBlocks` and their children - confirmed hands-on to have no
    `OriginalLayer`) live in local, symbol-relative coordinate space near
    the origin, nowhere near the real plan's placed-entity coordinates -
    mixing that space into one median/MAD pass makes hundreds of genuinely
    fine objects look like outliers relative to each other. Only
    layer-tagged, actually-placed entities belong in this statistic."""
    try:
        boxes = []
        for obj in doc.Objects:
            if layer_map.get(obj.Name) is None:
                continue
            if not hasattr(obj, "Shape") or obj.Shape.isNull():
                continue
            if getattr(obj, "ViewObject", None) is None:
                continue
            bb = obj.Shape.BoundBox
            if bb.XMin in (float("inf"), float("-inf")):
                continue
            boxes.append((obj, (bb.XMin + bb.XMax) / 2, (bb.YMin + bb.YMax) / 2))
        if len(boxes) < 4:
            return
        xs = [b[1] for b in boxes]
        ys = [b[2] for b in boxes]
        mx, my = ops._median(xs), ops._median(ys)
        mad_x = max(ops._median([abs(x - mx) for x in xs]), 1e-6)
        mad_y = max(ops._median([abs(y - my) for y in ys]), 1e-6)
        limit_x = mad_x * ops.OUTLIER_MAD_MULTIPLIER
        limit_y = mad_y * ops.OUTLIER_MAD_MULTIPLIER
        for obj, cx, cy in boxes:
            if abs(cx - mx) > limit_x or abs(cy - my) > limit_y:
                obj.ViewObject.Visibility = False
    except Exception:
        pass  # best-effort - never let a bad object block fitting the rest


def _fit_view(doc, layer_map: dict) -> None:
    """Frames the real geometry in a top-down (plan) view - hides
    BoundBox-outlier objects first (see _hide_boundbox_outliers), since a
    single such object blows fitAll()'s bounding box out to billions of mm,
    making the real geometry an invisible speck either way."""
    try:
        _hide_boundbox_outliers(doc, layer_map)
        av = FreeCADGui.ActiveDocument.ActiveView
        av.viewTop()
        av.fitAll()
    except Exception:
        pass  # best-effort - a missing/unready 3D view shouldn't fail the op


def _drain_queue(doc, layer_map: dict, last_id_box: list) -> None:
    """QTimer callback (main thread) - the only place doc/Draft/Gui state is
    touched. `last_id_box` is a 1-element list used as a mutable cell so
    $prev persists across every request this session ever handles."""
    while True:
        try:
            conn, request = REQUEST_QUEUE.get_nowait()
        except queue.Empty:
            return
        try:
            op_results, new_last_id = ops.run_ops(
                doc, layer_map, request.get("ops", []), last_id_box[0]
            )
            last_id_box[0] = new_last_id
            geometries, texts, objects, warnings, _dropped_ids = ops.extract(doc, layer_map)
            _fit_view(doc, layer_map)
            response = {
                "ok": True,
                "error": None,
                "op_results": op_results,
                "layers": sorted(set(layer_map.values())),
                "geometries": geometries,
                "texts": texts,
                "objects": objects,
                "warnings": warnings,
            }
        except Exception as exc:
            response = {
                "ok": False, "error": str(exc),
                "op_results": [], "layers": [], "geometries": [], "texts": [], "objects": [],
                "warnings": [],
            }
        try:
            conn.sendall(json.dumps(response).encode("utf-8"))
        finally:
            conn.close()


def main() -> None:
    dxf_path = os.environ["CRAFTSMAN_LIVE_INPUT"]
    port = int(os.environ["CRAFTSMAN_LIVE_PORT"])

    doc, layer_map = ops.open_and_prepare(dxf_path)
    FreeCADGui.showMainWindow()
    FreeCADGui.ActiveDocument = FreeCADGui.getDocument(doc.Name)
    _fit_view(doc, layer_map)

    threading.Thread(target=_accept_loop, args=(port,), daemon=True).start()

    last_id_box = [None]
    timer = QtCore.QTimer()
    timer.timeout.connect(lambda: _drain_queue(doc, layer_map, last_id_box))
    timer.start(POLL_INTERVAL_MS)
    # Keep a reference alive for the process lifetime - a QTimer with no
    # surviving Python reference can be garbage-collected out from under
    # the Qt event loop.
    FreeCAD.__craftsman_live_timer = timer


# FreeCAD (GUI) imports this file as a module named after its filename, same
# as FreeCADCmd does for worker.py (confirmed hands-on) - no __main__ guard.
# Startup errors are written to a log file, not just stderr - a GUI
# process's console output isn't always reachable (e.g. running under xpra
# as a --start-child), and a silent startup failure here is otherwise very
# hard to diagnose (confirmed hands-on while building this).
try:
    main()
except Exception:
    import traceback
    with open("/tmp/craftsman_live_session_error.log", "w") as f:
        traceback.print_exc(file=f)
    raise
