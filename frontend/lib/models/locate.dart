/// Dart mirror of the locate/analysis schemas in
/// `backend/app/models/schemas.py`.
library;

class LocateHit {
  const LocateHit({
    required this.label,
    required this.source,
    required this.confidence,
    required this.anchor,
    required this.worldBbox,
    this.layer,
    this.imageBbox,
  });

  final String label;
  final String source; // 'text' | 'layer'
  final double confidence;
  final String? layer;
  final List<double> anchor; // world coordinates
  final List<double> worldBbox;

  /// Normalized [x0, y0, x1, y1] on the render image, y-down.
  final List<double>? imageBbox;

  factory LocateHit.fromJson(Map<String, dynamic> json) => LocateHit(
        label: json['label'] as String,
        source: json['source'] as String,
        confidence: (json['confidence'] as num).toDouble(),
        layer: json['layer'] as String?,
        anchor: (json['anchor'] as List).map((v) => (v as num).toDouble()).toList(),
        worldBbox: (json['world_bbox'] as List)
            .map((v) => (v as num).toDouble())
            .toList(),
        imageBbox: (json['image_bbox'] as List?)
            ?.map((v) => (v as num).toDouble())
            .toList(),
      );

  /// Wire format for analyze/describe round-trips.
  Map<String, dynamic> toJson() => {
        'label': label,
        'source': source,
        'confidence': confidence,
        'layer': layer,
        'anchor': anchor,
        'world_bbox': worldBbox,
        'image_bbox': imageBbox,
      };
}

class HitAnalysis {
  const HitAnalysis({
    required this.entityCount,
    required this.entitiesByKind,
    required this.layers,
    required this.annotations,
    required this.metricsSummary,
    required this.bboxSize,
  });

  final int entityCount;
  final Map<String, int> entitiesByKind;
  final List<String> layers;
  final List<String> annotations;
  final String metricsSummary;
  final List<double> bboxSize;

  String get overviewLine {
    final kinds = entitiesByKind.entries.map((e) => '${e.value} ${e.key}').join(', ');
    return '$entityCount entities${kinds.isEmpty ? '' : ' ($kinds)'} · '
        '${layers.length} layers · ${annotations.length} annotations';
  }

  factory HitAnalysis.fromJson(Map<String, dynamic> json) => HitAnalysis(
        entityCount: json['entity_count'] as int,
        entitiesByKind: (json['entities_by_kind'] as Map<String, dynamic>)
            .map((k, v) => MapEntry(k, v as int)),
        layers: (json['layers'] as List).cast<String>(),
        annotations: (json['annotations'] as List).cast<String>(),
        metricsSummary: json['metrics_summary'] as String,
        bboxSize: (json['bbox_size'] as List)
            .map((v) => (v as num).toDouble())
            .toList(),
      );
}

class LocateResult {
  const LocateResult({
    required this.query,
    required this.hits,
    this.renderSize,
  });

  final String query;
  final List<LocateHit> hits;

  /// Render image pixel size [w, h]; drives the aspect-true overlay.
  final List<int>? renderSize;

  double get renderAspect => renderSize != null && renderSize![1] != 0
      ? renderSize![0] / renderSize![1]
      : 4 / 3;

  factory LocateResult.fromJson(Map<String, dynamic> json) => LocateResult(
        query: json['query'] as String,
        hits: [
          for (final h in json['hits'] as List)
            LocateHit.fromJson(h as Map<String, dynamic>),
        ],
        renderSize:
            (json['render_size'] as List?)?.map((v) => v as int).toList(),
      );
}
