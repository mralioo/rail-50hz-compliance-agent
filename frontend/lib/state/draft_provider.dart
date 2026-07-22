import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../models/draft.dart';

/// Draw-mode state: planner-clicked points (normalized render coords) and
/// the sketch elements the draftsman agent has drawn from them.
class DraftState {
  const DraftState({
    this.drawMode = false,
    this.points = const [],
    this.elements = const [],
    this.renderSize,
  });

  final bool drawMode;
  final List<Offset> points; // normalized [0..1], y-down
  final List<DrawnElement> elements;
  final List<int>? renderSize; // px [w, h] from /render/meta

  double? get renderAspect => renderSize != null && renderSize![1] != 0
      ? renderSize![0] / renderSize![1]
      : null;

  DraftState copyWith({
    bool? drawMode,
    List<Offset>? points,
    List<DrawnElement>? elements,
    List<int>? renderSize,
  }) =>
      DraftState(
        drawMode: drawMode ?? this.drawMode,
        points: points ?? this.points,
        elements: elements ?? this.elements,
        renderSize: renderSize ?? this.renderSize,
      );
}

class DraftNotifier extends Notifier<DraftState> {
  String? _metaJobId;

  @override
  DraftState build() => const DraftState();

  void toggleDrawMode() => state = state.copyWith(drawMode: !state.drawMode);

  void addPoint(Offset normalized) =>
      state = state.copyWith(points: [...state.points, normalized]);

  void undoPoint() {
    if (state.points.isEmpty) return;
    state = state.copyWith(
        points: state.points.sublist(0, state.points.length - 1));
  }

  void clearPoints() => state = state.copyWith(points: const []);

  void addElement(DrawnElement element) => state = state.copyWith(
        elements: [...state.elements, element],
        points: const [], // consumed by the drawn element
      );

  void removeElement(String id) => state = state.copyWith(
      elements: [for (final e in state.elements) if (e.id != id) e]);

  void reset() {
    _metaJobId = null;
    state = const DraftState();
  }

  /// Fetch the render pixel size once per job (canvas aspect mapping).
  Future<void> ensureMeta(String jobId) async {
    if (_metaJobId == jobId) return;
    _metaJobId = jobId;
    try {
      final meta = await ref.read(apiClientProvider).renderMeta(jobId);
      state = state.copyWith(renderSize: meta);
    } catch (_) {
      _metaJobId = null; // retry on next call
    }
  }
}

final draftProvider =
    NotifierProvider<DraftNotifier, DraftState>(DraftNotifier.new);
