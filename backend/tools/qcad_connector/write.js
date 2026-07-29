/**
 * QCAD connector: build a document from a JSON drawing spec and export it
 * to DXF.
 *
 * Consumes the same JSON shape tools/acadsharp_cli's `write` command takes
 * (ParsedDrawing.model_dump() from app/cad_engines/base.py), so the write
 * side of app/cad_engines/qcad_engine.py needs no translation layer.
 *
 * Run with:
 *   qcadcmd -no-gui -platform offscreen \
 *       -autostart tools/qcad_connector/write.js <spec.json> <output.dxf> [version] -quit
 *
 * `version`: "r12" selects QCAD's legacy AC1009 DXF writer; anything else
 * (including omitted) uses QCAD's default AC1015/R2000 writer - see the note
 * in docs/QCAD_CONNECTOR.md: QCAD's open-source dxflib-based exporter only
 * actually distinguishes those two cases internally (RDxfExporter.cpp), so
 * higher version labels don't produce a different byte format today.
 *
 * API grounded in examples/scripts/createdrawing.js and createlayer.js (the
 * officially bundled offscreen-document examples) plus scripts/simple.js's
 * addLayer/addLine/addCircle/addPolyline/addSimpleText helpers.
 */
include("scripts/simple.js");

function addGeometry(doc, g) {
    doc.setCurrentLayer(g.layer);
    if (g.kind === "line") {
        addLine(g.points[0], g.points[1]);
    }
    else if (g.kind === "circle") {
        addCircle(g.points[0], g.radius);
    }
    else if (g.kind === "polyline") {
        addPolyline(g.points, g.closed === true);
    }
    else {
        qWarning("qcad_connector/write: unsupported geometry kind:", g.kind);
    }
}

function addTextItem(doc, t) {
    doc.setCurrentLayer(t.layer);
    // 0.2 text height matches app/cad_engines/ezdxf_engine.py's default, so
    // the same spec renders at the same scale regardless of writing engine.
    addSimpleText(t.text, t.position, 0.2);
}

function main() {
    if (args.length < 3) {
        print("Usage: qcadcmd -no-gui -platform offscreen -autostart write.js <spec.json> <output-file> [version] -quit");
        return;
    }

    var version = "r2000";
    var specFile, outputFile;
    if (args.length >= 4) {
        version = args[args.length - 1];
        outputFile = args[args.length - 2];
        specFile = args[args.length - 3];
    } else {
        outputFile = args[args.length - 1];
        specFile = args[args.length - 2];
    }

    if (!new QFileInfo(specFile).isAbsolute()) {
        specFile = RSettings.getLaunchPath() + QDir.separator + specFile;
    }
    if (!new QFileInfo(outputFile).isAbsolute()) {
        outputFile = RSettings.getLaunchPath() + QDir.separator + outputFile;
    }

    var specText = readTextFile(specFile);
    if (isNull(specText)) {
        qWarning("qcad_connector/write: cannot read spec:", specFile);
        return;
    }
    var spec = JSON.parse(specText);

    var doc = createDocument();

    startTransaction(doc);
    for (var li = 0; li < spec.layers.length; ++li) {
        if (!doc.hasLayer(spec.layers[li])) {
            addLayer(spec.layers[li]);
        }
    }
    endTransaction();

    startTransaction(doc);
    for (var gi = 0; gi < spec.geometries.length; ++gi) {
        addGeometry(doc, spec.geometries[gi]);
    }
    for (var ti = 0; ti < spec.texts.length; ++ti) {
        addTextItem(doc, spec.texts[ti]);
    }
    endTransaction();

    var di = new RDocumentInterface(doc);
    var filter = (version === "r12") ? "R12 DXF" : "DXF";
    if (!di.exportFile(outputFile, filter)) {
        qWarning("qcad_connector/write: export failed:", outputFile);
        return;
    }

    print("qcad_connector/write: " + spec.geometries.length + " geometries, " +
          spec.texts.length + " texts -> " + outputFile);
}

if (typeof(including) == 'undefined' || including === false) {
    main();
}
