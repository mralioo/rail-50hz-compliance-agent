import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../models/job.dart';

/// Zoomable/pannable CAD viewport (feature_2 sandbox spec):
/// InteractiveViewer with 0.1x–25x zoom, double-tap to reset, and a
/// semantic layer→color classification adapted to real DB layer names.
class PlanCanvas extends StatefulWidget {
  const PlanCanvas({super.key, required this.payload, this.hiddenLayers});

  final DataLayerPayload payload;
  final Set<String>? hiddenLayers;

  @override
  State<PlanCanvas> createState() => _PlanCanvasState();
}

class _PlanCanvasState extends State<PlanCanvas> {
  final _transform = TransformationController();

  @override
  void dispose() {
    _transform.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: Container(
        color: const Color(0xFF14181D),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final size = Size(constraints.maxWidth, constraints.maxHeight);
            return Stack(
              children: [
                GestureDetector(
                  onDoubleTap: () => _transform.value = Matrix4.identity(),
                  child: InteractiveViewer(
                    transformationController: _transform,
                    minScale: 0.1,
                    maxScale: 25.0,
                    boundaryMargin: const EdgeInsets.all(double.infinity),
                    child: CustomPaint(
                      size: size,
                      painter: _PlanPainter(
                        widget.payload,
                        hiddenLayers: widget.hiddenLayers ?? const {},
                      ),
                    ),
                  ),
                ),
                Positioned(
                  right: 8,
                  bottom: 8,
                  child: Text(
                    'scroll/pinch to zoom · drag to pan · double-tap to reset',
                    style: TextStyle(
                      fontSize: 10,
                      color: Colors.white.withValues(alpha: 0.4),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

/// Semantic color classes for railway planning layers. Ordered rules; first
/// match wins. Falls back to a stable per-layer palette for unknown names.
Color layerColor(String layer, List<String> allLayers) {
  final l = layer.toLowerCase();
  // 50 Hz cabling — the payload's core content, highlighted strongest
  if (l.contains('leitung') || l.contains('kabel') || l.contains('cable') || l.contains('50hz')) {
    return const Color(0xFFD32F2F); // red
  }
  // Electrical equipment / signalling (EEA, LST)
  if (l.contains('eea') || l.contains('lst')) {
    return const Color(0xFF1976D2); // blue
  }
  // New planning
  if (l.contains('planung')) {
    return const Color(0xFF388E3C); // green
  }
  // Demolition / removal
  if (l.contains('rückbau') || l.contains('rueckbau')) {
    return const Color(0xFFF57C00); // orange
  }
  // Existing structures, tracks, streets — neutral context
  if (l.contains('bestand') || l.contains('street') || l.contains('strasse') ||
      l.contains('gleis') || l.contains('bue')) {
    return const Color(0xFF9E9E9E); // grey
  }
  // Sheet furniture: frames, legends, logos — dimmed
  if (l.contains('frame') || l.contains('legende') || l.contains('logo') ||
      l.contains('layout')) {
    return Colors.white24;
  }
  return _fallbackPalette[allLayers.indexOf(layer).abs() % _fallbackPalette.length];
}

const _fallbackPalette = <Color>[
  Color(0xFF62A0EA),
  Color(0xFFF66151),
  Color(0xFF8FF0A4),
  Color(0xFFF9F06B),
  Color(0xFFDC8ADD),
  Color(0xFFFFBE6F),
];

class _PlanPainter extends CustomPainter {
  _PlanPainter(this.payload, {this.hiddenLayers = const {}});

  final DataLayerPayload payload;
  final Set<String> hiddenLayers;

  @override
  void paint(Canvas canvas, Size size) {
    final bounds = payload.bounds;
    if (bounds == null) return;

    const margin = 24.0;
    final (minX, minY, maxX, maxY) = bounds;
    final worldW = (maxX - minX).abs().clamp(1e-6, double.infinity);
    final worldH = (maxY - minY).abs().clamp(1e-6, double.infinity);
    // Uniform scale preserves the drawing's aspect ratio (spec: scale-preserving)
    final scale = ((size.width - 2 * margin) / worldW)
        .clamp(0.0, (size.height - 2 * margin) / worldH);

    Offset toScreen(double x, double y) => Offset(
          margin + (x - minX) * scale,
          size.height - margin - (y - minY) * scale, // flip Y (CAD is Y-up)
        );

    for (final geo in payload.geometries) {
      if (hiddenLayers.contains(geo.layer)) continue;
      final paint = Paint()
        ..color = layerColor(geo.layer, payload.layers)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2;

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
      if (hiddenLayers.contains(item.layer)) continue;
      final painter = TextPainter(
        text: TextSpan(text: item.text, style: textStyle),
        textDirection: TextDirection.ltr,
      )..layout();
      painter.paint(canvas, toScreen(item.position.$1, item.position.$2));
    }
  }

  @override
  bool shouldRepaint(_PlanPainter oldDelegate) =>
      oldDelegate.payload != payload ||
      !setEquals(oldDelegate.hiddenLayers, hiddenLayers);
}
