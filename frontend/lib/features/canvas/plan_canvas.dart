import 'package:flutter/material.dart';

import '../../models/job.dart';

/// Paints the extracted geometry (shapely/ezdxf output) scaled to fit,
/// with the CAD Y-axis flipped to screen coordinates.
class PlanCanvas extends StatelessWidget {
  const PlanCanvas({super.key, required this.payload});

  final DataLayerPayload payload;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: Container(
        color: const Color(0xFF14181D),
        child: CustomPaint(
          painter: _PlanPainter(payload),
          size: Size.infinite,
        ),
      ),
    );
  }
}

class _PlanPainter extends CustomPainter {
  _PlanPainter(this.payload);

  final DataLayerPayload payload;

  static const _layerColors = <Color>[
    Color(0xFF62A0EA), // blue
    Color(0xFFF66151), // red
    Color(0xFF8FF0A4), // green
    Color(0xFFF9F06B), // yellow
    Color(0xFFDC8ADD), // purple
    Color(0xFFFFBE6F), // orange
  ];

  Color _colorFor(String layer) =>
      _layerColors[payload.layers.indexOf(layer).abs() % _layerColors.length];

  @override
  void paint(Canvas canvas, Size size) {
    final bounds = payload.bounds;
    if (bounds == null) return;

    const margin = 24.0;
    final (minX, minY, maxX, maxY) = bounds;
    final worldW = (maxX - minX).abs().clamp(1e-6, double.infinity);
    final worldH = (maxY - minY).abs().clamp(1e-6, double.infinity);
    final scale = ((size.width - 2 * margin) / worldW)
        .clamp(0.0, (size.height - 2 * margin) / worldH);

    Offset toScreen(double x, double y) => Offset(
          margin + (x - minX) * scale,
          size.height - margin - (y - minY) * scale, // flip Y
        );

    for (final geo in payload.geometries) {
      final paint = Paint()
        ..color = _colorFor(geo.layer)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6;

      if (geo.kind == 'circle' && geo.radius != null) {
        final (cx, cy) = geo.points.first;
        canvas.drawCircle(toScreen(cx, cy), geo.radius! * scale, paint);
        continue;
      }
      if (geo.points.length < 2) continue;

      final path = Path()
        ..moveTo(toScreen(geo.points.first.$1, geo.points.first.$2).dx,
            toScreen(geo.points.first.$1, geo.points.first.$2).dy);
      for (final (x, y) in geo.points.skip(1)) {
        final p = toScreen(x, y);
        path.lineTo(p.dx, p.dy);
      }
      if (geo.closed) path.close();
      canvas.drawPath(path, paint);
    }

    final textStyle = TextStyle(
      color: Colors.white.withValues(alpha: 0.85),
      fontSize: 11,
    );
    for (final item in payload.texts) {
      final painter = TextPainter(
        text: TextSpan(text: item.text, style: textStyle),
        textDirection: TextDirection.ltr,
      )..layout();
      painter.paint(canvas, toScreen(item.position.$1, item.position.$2));
    }
  }

  @override
  bool shouldRepaint(_PlanPainter oldDelegate) =>
      oldDelegate.payload != payload;
}
