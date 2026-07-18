/// Dart mirror of `backend/app/models/schemas.py` — keep in sync.
library;

enum JobStatus {
  queued,
  converting,
  extracting,
  analyzing,
  ready,
  failed;

  static JobStatus fromWire(String value) =>
      JobStatus.values.firstWhere((s) => s.name == value);

  String get label => switch (this) {
        queued => 'Queued',
        converting => 'Converting (DWG → DXF)',
        extracting => 'Extracting Geometry',
        analyzing => 'AI Compliance Analysis',
        ready => 'Ready',
        failed => 'Failed',
      };
}

class Geometry {
  const Geometry({
    required this.layer,
    required this.kind,
    required this.points,
    this.closed = false,
    this.radius,
  });

  final String layer;
  final String kind; // polyline | line | circle
  final List<(double, double)> points;
  final bool closed;
  final double? radius;

  factory Geometry.fromJson(Map<String, dynamic> json) => Geometry(
        layer: json['layer'] as String,
        kind: json['kind'] as String,
        points: [
          for (final p in json['points'] as List)
            ((p[0] as num).toDouble(), (p[1] as num).toDouble()),
        ],
        closed: json['closed'] as bool? ?? false,
        radius: (json['radius'] as num?)?.toDouble(),
      );
}

class TextItem {
  const TextItem({required this.layer, required this.text, required this.position});

  final String layer;
  final String text;
  final (double, double) position;

  factory TextItem.fromJson(Map<String, dynamic> json) => TextItem(
        layer: json['layer'] as String,
        text: json['text'] as String,
        position: (
          (json['position'][0] as num).toDouble(),
          (json['position'][1] as num).toDouble(),
        ),
      );
}

class Metric {
  const Metric({required this.name, required this.value, required this.unit, this.layer});

  final String name;
  final double value;
  final String unit;
  final String? layer;

  factory Metric.fromJson(Map<String, dynamic> json) => Metric(
        name: json['name'] as String,
        value: (json['value'] as num).toDouble(),
        unit: json['unit'] as String,
        layer: json['layer'] as String?,
      );
}

class DataLayerPayload {
  const DataLayerPayload({
    required this.sourceFile,
    required this.layers,
    required this.geometries,
    required this.texts,
    required this.metrics,
    this.bounds,
  });

  final String sourceFile;
  final List<String> layers;
  final List<Geometry> geometries;
  final List<TextItem> texts;
  final List<Metric> metrics;
  final (double, double, double, double)? bounds;

  factory DataLayerPayload.fromJson(Map<String, dynamic> json) => DataLayerPayload(
        sourceFile: json['source_file'] as String,
        layers: (json['layers'] as List).cast<String>(),
        geometries: [
          for (final g in json['geometries'] as List)
            Geometry.fromJson(g as Map<String, dynamic>),
        ],
        texts: [
          for (final t in json['texts'] as List)
            TextItem.fromJson(t as Map<String, dynamic>),
        ],
        metrics: [
          for (final m in json['metrics'] as List)
            Metric.fromJson(m as Map<String, dynamic>),
        ],
        bounds: json['bounds'] == null
            ? null
            : (
                (json['bounds'][0] as num).toDouble(),
                (json['bounds'][1] as num).toDouble(),
                (json['bounds'][2] as num).toDouble(),
                (json['bounds'][3] as num).toDouble(),
              ),
      );
}

class Finding {
  const Finding({
    required this.status,
    required this.parameter,
    required this.actual,
    required this.expected,
    required this.regulation,
    this.location,
    this.suggestion,
  });

  final String status; // compliant | non_compliant | warning
  final String parameter;
  final String actual;
  final String expected;
  final String regulation;
  final String? location;
  final String? suggestion;

  bool get isCompliant => status == 'compliant';

  factory Finding.fromJson(Map<String, dynamic> json) => Finding(
        status: json['status'] as String,
        parameter: json['parameter'] as String,
        actual: json['actual'] as String,
        expected: json['expected'] as String,
        regulation: json['regulation'] as String,
        location: json['location'] as String?,
        suggestion: json['suggestion'] as String?,
      );
}

class ComplianceReport {
  const ComplianceReport({required this.findings, required this.summary});

  final List<Finding> findings;
  final String summary;

  factory ComplianceReport.fromJson(Map<String, dynamic> json) => ComplianceReport(
        findings: [
          for (final f in json['findings'] as List)
            Finding.fromJson(f as Map<String, dynamic>),
        ],
        summary: json['summary'] as String? ?? '',
      );
}

class Job {
  const Job({
    required this.id,
    required this.status,
    required this.filename,
    this.error,
    this.payload,
    this.report,
  });

  final String id;
  final JobStatus status;
  final String filename;
  final String? error;
  final DataLayerPayload? payload;
  final ComplianceReport? report;

  factory Job.fromJson(Map<String, dynamic> json) => Job(
        id: json['id'] as String,
        status: JobStatus.fromWire(json['status'] as String),
        filename: json['filename'] as String,
        error: json['error'] as String?,
        payload: json['payload'] == null
            ? null
            : DataLayerPayload.fromJson(json['payload'] as Map<String, dynamic>),
        report: json['report'] == null
            ? null
            : ComplianceReport.fromJson(json['report'] as Map<String, dynamic>),
      );
}
