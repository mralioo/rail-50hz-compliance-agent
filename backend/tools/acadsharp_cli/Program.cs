// Minimal CLI shim around ACadSharp (https://github.com/DomCR/ACadSharp), invoked as a
// subprocess from the Python backend's `acadsharp_engine.py` adapter - the same pattern
// already used for LibreDWG's dwg2dxf/dxf2dwg. Exists purely to test ACadSharp as a
// candidate read/write engine; see docs/CAD_ENGINE_FRAMEWORK.md.
//
// Commands:
//   read    <in.dwg|in.dxf> <out.json>                 dump entities to our interchange JSON
//   write   <spec.json> <out.dwg|out.dxf> [version]     build a document from JSON and save it
//   convert <in.dwg|in.dxf> <out.dwg|out.dxf> [version]  read then re-save (format/version change)
//
// version: r2000 | r2004 | r2007 | r2010 | r2013 | r2018 (default r2018), matching the
// naming already used for LibreDWG's dxf2dwg --as flag.
using System.Text.Json;
using System.Text.Json.Serialization;
using ACadSharp;
using ACadSharp.Entities;
using ACadSharp.IO;
using ACadSharp.Tables;
using CSMath;

namespace AcadSharpCli;

public class GeometrySpec
{
    public string Layer { get; set; } = "0";
    public string Kind { get; set; } = "line"; // line | polyline | circle
    public List<double[]> Points { get; set; } = new();
    public bool Closed { get; set; }
    public double? Radius { get; set; }
}

public class TextSpec
{
    public string Layer { get; set; } = "0";
    public string Text { get; set; } = "";
    public double[] Position { get; set; } = new double[] { 0, 0 };
}

public class DrawingSpec
{
    public List<string> Layers { get; set; } = new();
    public List<GeometrySpec> Geometries { get; set; } = new();
    public List<TextSpec> Texts { get; set; } = new();
}

public static class Program
{
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        WriteIndented = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private static readonly Dictionary<string, ACadVersion> Versions = new()
    {
        ["r2000"] = ACadVersion.AC1015,
        ["r2004"] = ACadVersion.AC1018,
        ["r2007"] = ACadVersion.AC1021,
        ["r2010"] = ACadVersion.AC1024,
        ["r2013"] = ACadVersion.AC1027,
        ["r2018"] = ACadVersion.AC1032,
    };

    public static int Main(string[] args)
    {
        try
        {
            if (args.Length < 1) throw new ArgumentException("Usage: acadsharp_cli <read|write|convert> ...");
            switch (args[0])
            {
                case "read":
                    return CmdRead(args[1], args[2]);
                case "write":
                    return CmdWrite(args[1], args[2], args.Length > 3 ? args[3] : "r2018");
                case "convert":
                    return CmdConvert(args[1], args[2], args.Length > 3 ? args[3] : "r2018");
                default:
                    throw new ArgumentException($"Unknown command: {args[0]}");
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"ERROR: {ex.GetType().Name}: {ex.Message}");
            return 1;
        }
    }

    private static CadDocument ReadDoc(string path)
    {
        var notifications = new List<string>();
        void OnNotify(object? s, NotificationEventArgs e) => notifications.Add($"[{e.NotificationType}] {e.Message}");

        CadDocument doc;
        if (path.EndsWith(".dwg", StringComparison.OrdinalIgnoreCase))
        {
            using var reader = new DwgReader(path);
            reader.OnNotification += OnNotify;
            doc = reader.Read();
        }
        else
        {
            using var reader = new DxfReader(path);
            reader.OnNotification += OnNotify;
            doc = reader.Read();
        }
        foreach (var n in notifications) Console.Error.WriteLine(n);
        return doc;
    }

    private static void WriteDoc(CadDocument doc, string path)
    {
        if (path.EndsWith(".dwg", StringComparison.OrdinalIgnoreCase))
        {
            using var writer = new DwgWriter(path, doc);
            writer.OnNotification += (s, e) => Console.Error.WriteLine($"[{e.NotificationType}] {e.Message}");
            writer.Write();
        }
        else
        {
            using var writer = new DxfWriter(path, doc, false);
            writer.OnNotification += (s, e) => Console.Error.WriteLine($"[{e.NotificationType}] {e.Message}");
            writer.Write();
        }
    }

    private static int CmdRead(string inPath, string outJsonPath)
    {
        CadDocument doc = ReadDoc(inPath);
        var spec = new DrawingSpec
        {
            Layers = doc.Layers.Select(l => l.Name).OrderBy(n => n).ToList(),
        };

        foreach (Entity e in doc.Entities)
        {
            switch (e)
            {
                case Line line:
                    spec.Geometries.Add(new GeometrySpec
                    {
                        Layer = line.Layer.Name,
                        Kind = "line",
                        Points = new List<double[]>
                        {
                            new[] { line.StartPoint.X, line.StartPoint.Y },
                            new[] { line.EndPoint.X, line.EndPoint.Y },
                        },
                    });
                    break;
                case LwPolyline poly:
                    spec.Geometries.Add(new GeometrySpec
                    {
                        Layer = poly.Layer.Name,
                        Kind = "polyline",
                        Points = poly.Vertices.Select(v => new[] { v.Location.X, v.Location.Y }).ToList(),
                        Closed = poly.IsClosed,
                    });
                    break;
                case Circle circle:
                    spec.Geometries.Add(new GeometrySpec
                    {
                        Layer = circle.Layer.Name,
                        Kind = "circle",
                        Points = new List<double[]> { new[] { circle.Center.X, circle.Center.Y } },
                        Radius = circle.Radius,
                    });
                    break;
                case TextEntity text:
                    spec.Texts.Add(new TextSpec
                    {
                        Layer = text.Layer.Name,
                        Text = text.Value,
                        Position = new[] { text.InsertPoint.X, text.InsertPoint.Y },
                    });
                    break;
                case MText mtext:
                    spec.Texts.Add(new TextSpec
                    {
                        Layer = mtext.Layer.Name,
                        Text = mtext.Value,
                        Position = new[] { mtext.InsertPoint.X, mtext.InsertPoint.Y },
                    });
                    break;
                // other entity kinds (HATCH, SPLINE, INSERT, DIMENSION, ...) intentionally
                // uncounted here - this shim only needs the subset our own extraction
                // pipeline understands (dxf_parser.py), for apples-to-apples comparison.
            }
        }

        File.WriteAllText(outJsonPath, JsonSerializer.Serialize(spec, JsonOpts));
        Console.WriteLine($"SUCCESS layers={spec.Layers.Count} geometries={spec.Geometries.Count} texts={spec.Texts.Count}");
        return 0;
    }

    private static CadDocument BuildDoc(DrawingSpec spec, ACadVersion version)
    {
        var doc = new CadDocument(version);
        var layers = new Dictionary<string, Layer>();
        foreach (var name in spec.Layers)
        {
            // a fresh CadDocument already has default layers (e.g. "0") -
            // Layers.Add throws on a duplicate key, which a read-then-write
            // round trip hits immediately since every DWG has layer "0".
            var existing = doc.Layers.FirstOrDefault(x => x.Name == name);
            if (existing != null)
            {
                layers[name] = existing;
                continue;
            }
            var layer = new Layer(name);
            doc.Layers.Add(layer);
            layers[name] = layer;
        }
        Layer LayerFor(string name) => layers.TryGetValue(name, out var l) ? l : doc.Layers.FirstOrDefault(x => x.Name == name) ?? Layer.Default;

        foreach (var g in spec.Geometries)
        {
            Entity entity = g.Kind switch
            {
                "line" => new Line
                {
                    StartPoint = new XYZ(g.Points[0][0], g.Points[0][1], 0),
                    EndPoint = new XYZ(g.Points[1][0], g.Points[1][1], 0),
                },
                "polyline" => new LwPolyline(g.Points.Select(p => new XY(p[0], p[1]))) { IsClosed = g.Closed },
                "circle" => new Circle
                {
                    Center = new XYZ(g.Points[0][0], g.Points[0][1], 0),
                    Radius = g.Radius ?? 0.1,
                },
                _ => throw new ArgumentException($"Unsupported geometry kind: {g.Kind}"),
            };
            entity.Layer = LayerFor(g.Layer);
            doc.Entities.Add(entity);
        }

        foreach (var t in spec.Texts)
        {
            var text = new TextEntity
            {
                Value = t.Text,
                InsertPoint = new XYZ(t.Position[0], t.Position[1], 0),
                Height = 0.2,
                Layer = LayerFor(t.Layer),
            };
            doc.Entities.Add(text);
        }

        return doc;
    }

    private static int CmdWrite(string specJsonPath, string outPath, string versionKey)
    {
        if (!Versions.TryGetValue(versionKey, out var version))
            throw new ArgumentException($"Unknown version '{versionKey}', expected one of: {string.Join(", ", Versions.Keys)}");

        var spec = JsonSerializer.Deserialize<DrawingSpec>(File.ReadAllText(specJsonPath), JsonOpts)
                   ?? throw new ArgumentException("Empty/invalid spec JSON");
        CadDocument doc = BuildDoc(spec, version);
        WriteDoc(doc, outPath);
        Console.WriteLine($"SUCCESS wrote {outPath} as {versionKey} ({version})");
        return 0;
    }

    private static int CmdConvert(string inPath, string outPath, string versionKey)
    {
        if (!Versions.TryGetValue(versionKey, out var version))
            throw new ArgumentException($"Unknown version '{versionKey}', expected one of: {string.Join(", ", Versions.Keys)}");

        CadDocument doc = ReadDoc(inPath);
        doc.Header.Version = version;
        WriteDoc(doc, outPath);
        Console.WriteLine($"SUCCESS converted {inPath} -> {outPath} as {versionKey} ({version})");
        return 0;
    }
}
