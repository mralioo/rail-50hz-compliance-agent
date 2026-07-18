import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../models/locate.dart';
import 'pipeline_provider.dart';

/// One locator hit plus its UI/analysis state in the findings panel.
class HitState {
  const HitState({
    required this.hit,
    this.visible = true,
    this.analysis,
    this.description,
    this.describing = false,
  });

  final LocateHit hit;
  final bool visible; // box shown on the canvas
  final HitAnalysis? analysis; // deterministic overview (auto-fetched)
  final String? description; // AI text (fetched only on user click)
  final bool describing;

  HitState copyWith({
    bool? visible,
    HitAnalysis? analysis,
    String? description,
    bool? describing,
  }) =>
      HitState(
        hit: hit,
        visible: visible ?? this.visible,
        analysis: analysis ?? this.analysis,
        description: description ?? this.description,
        describing: describing ?? this.describing,
      );
}

class LocateSession {
  const LocateSession({
    required this.query,
    required this.hits,
    this.renderSize,
    this.selected,
  });

  final String query;
  final List<HitState> hits;
  final List<int>? renderSize;
  final int? selected; // index of the highlighted finding

  double get renderAspect => renderSize != null && renderSize![1] != 0
      ? renderSize![0] / renderSize![1]
      : 4 / 3;

  LocateSession copyWith({List<HitState>? hits, int? selected, bool clearSelected = false}) =>
      LocateSession(
        query: query,
        hits: hits ?? this.hits,
        renderSize: renderSize,
        selected: clearSelected ? null : (selected ?? this.selected),
      );
}

/// Locator results + per-hit analysis state. Deterministic overviews are
/// fetched automatically (local math, no LLM); AI descriptions only on click.
class LocateNotifier extends Notifier<LocateSession?> {
  @override
  LocateSession? build() => null;

  void show(LocateResult result) {
    state = LocateSession(
      query: result.query,
      renderSize: result.renderSize,
      hits: [for (final h in result.hits) HitState(hit: h)],
    );
    _fetchAnalyses();
  }

  void clear() => state = null;

  void toggleVisible(int index) => _update(index, (h) => h.copyWith(visible: !h.visible));

  void setAllVisible(bool visible) {
    final session = state;
    if (session == null) return;
    state = session.copyWith(
      hits: [for (final h in session.hits) h.copyWith(visible: visible)],
    );
  }

  void select(int? index) =>
      state = state?.copyWith(selected: index, clearSelected: index == null);

  Future<void> describe(int index) async {
    final session = state;
    final jobId = ref.read(pipelineProvider).job?.id;
    if (session == null || jobId == null) return;
    final hitState = session.hits[index];
    if (hitState.describing || hitState.description != null) return; // no re-spend

    _update(index, (h) => h.copyWith(describing: true));
    try {
      final text =
          await ref.read(apiClientProvider).describeHit(jobId, hitState.hit);
      _update(index, (h) => h.copyWith(description: text, describing: false));
    } catch (e) {
      _update(
        index,
        (h) => h.copyWith(description: 'Description failed: $e', describing: false),
      );
    }
  }

  Future<void> _fetchAnalyses() async {
    final session = state;
    final jobId = ref.read(pipelineProvider).job?.id;
    if (session == null || jobId == null || session.hits.isEmpty) return;
    try {
      final analyses = await ref
          .read(apiClientProvider)
          .analyzeHits(jobId, [for (final h in session.hits) h.hit]);
      final current = state;
      if (current == null || current.query != session.query) return; // stale
      state = current.copyWith(hits: [
        for (var i = 0; i < current.hits.length; i++)
          i < analyses.length
              ? current.hits[i].copyWith(analysis: analyses[i])
              : current.hits[i],
      ]);
    } catch (_) {
      // overview stays empty; rows still work
    }
  }

  void _update(int index, HitState Function(HitState) fn) {
    final session = state;
    if (session == null || index < 0 || index >= session.hits.length) return;
    state = session.copyWith(hits: [
      for (var i = 0; i < session.hits.length; i++)
        i == index ? fn(session.hits[i]) : session.hits[i],
    ]);
  }
}

final locateProvider =
    NotifierProvider<LocateNotifier, LocateSession?>(LocateNotifier.new);
