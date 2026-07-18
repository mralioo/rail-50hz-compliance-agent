import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/config.dart';
import '../../models/job.dart';
import '../../models/locate.dart';
import '../../state/locate_provider.dart';
import 'plan_canvas.dart';

enum PlanViewMode { vector, render }

/// Canvas area with a Vector/Render toggle:
/// - Vector: client-side CustomPainter over the extracted geometry
/// - Render: server-side ezdxf PNG (shows block symbols the extractor
///   doesn't traverse yet), zoomable like the vector view
///
/// Locator-agent hits ("where is the Betonschalthaus?") are drawn as
/// highlight boxes over the render image; per-hit visibility and selection
/// are controlled from the findings panel below the canvas.
class PlanViewer extends ConsumerStatefulWidget {
  const PlanViewer({super.key, required this.job});

  final Job job;

  @override
  ConsumerState<PlanViewer> createState() => _PlanViewerState();
}

class _PlanViewerState extends ConsumerState<PlanViewer> {
  PlanViewMode _mode = PlanViewMode.render;
  final _renderTransform = TransformationController();
  final Set<String> _hiddenLayers = {};

  String get _renderUrl {
    final base = '${AppConfig.apiBaseUrl}/api/v1/jobs/${widget.job.id}/render';
    final all = widget.job.payload?.layers ?? const <String>[];
    if (_hiddenLayers.isEmpty || all.isEmpty) return base;
    final visible = all.where((l) => !_hiddenLayers.contains(l));
    return '$base?layers=${Uri.encodeComponent(visible.join(','))}';
  }

  Widget _buildLayerFilter() {
    final layers = widget.job.payload?.layers ?? const <String>[];
    if (layers.isEmpty) return const SizedBox.shrink();
    return PopupMenuButton<String>(
      tooltip: 'Filter layers (render & vector views)',
      icon: Badge(
        isLabelVisible: _hiddenLayers.isNotEmpty,
        label: Text('${_hiddenLayers.length}'),
        child: const Icon(Icons.layers_outlined, size: 20),
      ),
      itemBuilder: (context) => [
        PopupMenuItem(
          onTap: () => setState(_hiddenLayers.clear),
          child: const Text('Show all layers'),
        ),
        const PopupMenuDivider(),
        for (final layer in layers)
          CheckedPopupMenuItem(
            checked: !_hiddenLayers.contains(layer),
            onTap: () => setState(() => _hiddenLayers.contains(layer)
                ? _hiddenLayers.remove(layer)
                : _hiddenLayers.add(layer)),
            child: Text(layer, style: const TextStyle(fontSize: 12)),
          ),
      ],
    );
  }

  @override
  void dispose() {
    _renderTransform.dispose();
    super.dispose();
  }

  Widget _buildRenderView(LocateSession? session) {
    final image = Image.network(
      _renderUrl,
      key: ValueKey(_renderUrl), // re-fetch when the layer filter changes
      fit: BoxFit.contain,
      errorBuilder: (context, error, stack) => const Padding(
        padding: EdgeInsets.all(24),
        child: Text('No server render available for this plan — '
            'switch to Vector view.'),
      ),
      loadingBuilder: (context, child, progress) => progress == null
          ? child
          : const Center(child: CircularProgressIndicator()),
    );

    return GestureDetector(
      onDoubleTap: () => _renderTransform.value = Matrix4.identity(),
      child: InteractiveViewer(
        transformationController: _renderTransform,
        minScale: 0.1,
        maxScale: 25.0,
        boundaryMargin: const EdgeInsets.all(double.infinity),
        child: Center(
          child: session == null
              ? image
              // AspectRatio matches the PNG exactly, so normalized hit
              // rects from the backend land on the right image spots.
              : AspectRatio(
                  aspectRatio: session.renderAspect,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      image,
                      CustomPaint(
                        painter: _HitOverlayPainter(
                          hits: [
                            for (final h in session.hits)
                              if (h.visible) h.hit,
                          ],
                          selectedHit: session.selected != null &&
                                  session.hits[session.selected!].visible
                              ? session.hits[session.selected!].hit
                              : null,
                        ),
                      ),
                    ],
                  ),
                ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final payload = widget.job.payload;
    final session = ref.watch(locateProvider);

    // New locator hits force the render view, where the boxes live.
    ref.listen(locateProvider, (previous, next) {
      if (next != null &&
          next.hits.isNotEmpty &&
          previous?.query != next.query) {
        setState(() => _mode = PlanViewMode.render);
      }
    });

    return ClipRRect(
      borderRadius: BorderRadius.circular(8),
      child: Container(
        color: const Color(0xFF14181D),
        child: Stack(
          children: [
            Positioned.fill(
              child: _mode == PlanViewMode.vector && payload != null
                  ? PlanCanvas(payload: payload, hiddenLayers: _hiddenLayers)
                  : _buildRenderView(session),
            ),
            Positioned(
              top: 8,
              right: 8,
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _buildLayerFilter(),
                  const SizedBox(width: 4),
                  SegmentedButton<PlanViewMode>(
                    style:
                        const ButtonStyle(visualDensity: VisualDensity.compact),
                    segments: const [
                      ButtonSegment(
                        value: PlanViewMode.render,
                        label: Text('Render'),
                        icon: Icon(Icons.image_outlined, size: 16),
                        tooltip: 'Full-fidelity server render (all symbols)',
                      ),
                      ButtonSegment(
                        value: PlanViewMode.vector,
                        label: Text('Vectors'),
                        icon: Icon(Icons.polyline_outlined, size: 16),
                        tooltip: 'Extracted data layer, semantic colors',
                      ),
                    ],
                    selected: {_mode},
                    onSelectionChanged: (selection) =>
                        setState(() => _mode = selection.first),
                  ),
                ],
              ),
            ),
            if (session != null)
              Positioned(
                top: 8,
                left: 8,
                child: Chip(
                  label: Text(
                    '${session.hits.where((h) => h.visible).length}/'
                    '${session.hits.length} shown: "${session.query}"',
                    style: const TextStyle(fontSize: 12),
                  ),
                  onDeleted: () => ref.read(locateProvider.notifier).clear(),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _HitOverlayPainter extends CustomPainter {
  _HitOverlayPainter({required this.hits, this.selectedHit});

  final List<LocateHit> hits;
  final LocateHit? selectedHit;

  static const _highlight = Color(0xFFFFC107); // amber
  static const _selected = Color(0xFFFF5722); // deep orange

  void _drawHit(Canvas canvas, Size size, LocateHit hit, bool isSelected) {
    final b = hit.imageBbox;
    if (b == null) return;
    final color = isSelected ? _selected : _highlight;
    final stroke = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = isSelected ? 3.0 : 2.0;
    final fill = Paint()..color = color.withValues(alpha: isSelected ? 0.25 : 0.15);

    var rect = Rect.fromLTRB(
      b[0] * size.width,
      b[1] * size.height,
      b[2] * size.width,
      b[3] * size.height,
    );
    // Keep tiny anchors visible and tappable at plan scale
    if (rect.width < 12 || rect.height < 12) {
      rect = Rect.fromCenter(
        center: rect.center,
        width: rect.width.clamp(12, double.infinity),
        height: rect.height.clamp(12, double.infinity),
      );
    }
    final rrect = RRect.fromRectAndRadius(rect, const Radius.circular(3));
    canvas.drawRRect(rrect, fill);
    canvas.drawRRect(rrect, stroke);

    final label = TextPainter(
      text: TextSpan(
        text: hit.label,
        style: TextStyle(
          color: Colors.black,
          fontSize: 9,
          fontWeight: FontWeight.w600,
          backgroundColor: color,
        ),
      ),
      textDirection: TextDirection.ltr,
      maxLines: 1,
      ellipsis: '…',
    )..layout(maxWidth: 200);
    label.paint(
      canvas,
      Offset(rect.left, (rect.top - label.height - 2).clamp(0, size.height)),
    );
  }

  @override
  void paint(Canvas canvas, Size size) {
    for (final hit in hits) {
      if (hit != selectedHit) _drawHit(canvas, size, hit, false);
    }
    if (selectedHit != null) {
      _drawHit(canvas, size, selectedHit!, true); // on top
    }
  }

  @override
  bool shouldRepaint(_HitOverlayPainter oldDelegate) =>
      oldDelegate.hits != hits || oldDelegate.selectedHit != selectedHit;
}
