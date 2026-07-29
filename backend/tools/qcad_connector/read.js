/**
 * QCAD connector: read a DXF file and dump layers/geometries/texts as JSON.
 *
 * Mirrors the JSON shape tools/acadsharp_cli's `read` command produces, so
 * app/cad_engines/qcad_engine.py can parse it with the same Geometry/TextItem
 * construction used for every other engine (app/cad_engines/base.py).
 *
 * Run with:
 *   qcadcmd -no-gui -platform offscreen \
 *       -autostart tools/qcad_connector/read.js <input.dxf> <output.json> -quit
 *
 * API grounded in QCAD's own scripts/Misc/Examples/CommandLineExamples/
 * ExSetColor/ExSetColor.js (the officially bundled command-line example) and
 * scripts/library.js's isLineEntity/isCircleEntity/isPolylineEntity/
 * isTextEntity + readTextFile/writeTextFile helpers.
 */
include("scripts/library.js");

function serializeEntity(entity, geometries, texts) {
    var layer = entity.getLayerName();

    if (isLineEntity(entity)) {
        var sp = entity.getStartPoint();
        var ep = entity.getEndPoint();
        geometries.push({
            layer: layer,
            kind: "line",
            points: [[sp.x, sp.y], [ep.x, ep.y]],
            closed: false,
            radius: null
        });
    }
    else if (isCircleEntity(entity)) {
        var c = entity.getCenter();
        geometries.push({
            layer: layer,
            kind: "circle",
            points: [[c.x, c.y]],
            closed: false,
            radius: entity.getRadius()
        });
    }
    else if (isPolylineEntity(entity)) {
        var pts = [];
        var n = entity.countVertices();
        for (var v = 0; v < n; ++v) {
            var vertex = entity.getVertexAt(v);
            pts.push([vertex.x, vertex.y]);
        }
        geometries.push({
            layer: layer,
            kind: "polyline",
            points: pts,
            closed: entity.isClosed(),
            radius: null
        });
    }
    else if (isTextEntity(entity)) {
        var pos = entity.getPosition();
        texts.push({
            layer: layer,
            text: entity.getText(),
            position: [pos.x, pos.y]
        });
    }
    // other entity types (HATCH, SPLINE, DIMENSION, INSERT, ...) intentionally
    // skipped for now - same subset every other cad_engines adapter covers,
    // see docs/CAD_ENGINE_FRAMEWORK.md section 5.
}

function main() {
    if (args.length < 3) {
        print("Usage: qcadcmd -no-gui -platform offscreen -autostart read.js <input-file> <output-json> -quit");
        return;
    }

    var inputFile = args[args.length - 2];
    var outputJson = args[args.length - 1];

    if (!new QFileInfo(inputFile).isAbsolute()) {
        inputFile = RSettings.getLaunchPath() + QDir.separator + inputFile;
    }
    if (!new QFileInfo(outputJson).isAbsolute()) {
        outputJson = RSettings.getLaunchPath() + QDir.separator + outputJson;
    }

    var doc = new RDocument(new RMemoryStorage(), new RSpatialIndexSimple());
    var di = new RDocumentInterface(doc);

    if (di.importFile(inputFile) !== RDocumentInterface.IoErrorNoError) {
        writeTextFile(outputJson, JSON.stringify({error: "import failed: " + inputFile}));
        qWarning("qcad_connector/read: cannot import file:", inputFile);
        return;
    }

    var layers = doc.getLayerNames();
    var geometries = [];
    var texts = [];

    var ids = doc.queryAllEntities();
    for (var i = 0; i < ids.length; ++i) {
        var entity = doc.queryEntity(ids[i]);
        if (isNull(entity)) {
            continue;
        }
        serializeEntity(entity, geometries, texts);
    }

    writeTextFile(outputJson, JSON.stringify({
        layers: layers,
        geometries: geometries,
        texts: texts
    }));

    print("qcad_connector/read: " + geometries.length + " geometries, " +
          texts.length + " texts -> " + outputJson);
}

if (typeof(including) == 'undefined' || including === false) {
    main();
}
