/// Dart mirror of the draftsman schemas in `backend/app/models/schemas.py`.
library;

class DrawnElement {
  const DrawnElement({
    required this.id,
    required this.kind,
    required this.label,
    required this.pointsImage,
    required this.length,
    required this.note,
  });

  final String id;
  final String kind;
  final String label;

  /// Normalized [0..1] render-image coordinates, y-down.
  final List<List<double>> pointsImage;
  final double length;
  final String note;

  factory DrawnElement.fromJson(Map<String, dynamic> json) => DrawnElement(
        id: json['id'] as String,
        kind: json['kind'] as String,
        label: json['label'] as String,
        pointsImage: [
          for (final p in json['points_image'] as List)
            [(p[0] as num).toDouble(), (p[1] as num).toDouble()],
        ],
        length: (json['length'] as num).toDouble(),
        note: json['note'] as String,
      );
}
