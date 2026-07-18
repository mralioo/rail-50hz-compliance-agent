import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/locate_provider.dart';

/// Bottom-panel deep dive on locator findings: each hit is a row with a
/// visibility toggle (its box on the canvas), a deterministic overview, and
/// an on-demand AI description ("Describe" — one click, one request).
class FindingsPanel extends ConsumerWidget {
  const FindingsPanel({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(locateProvider);
    if (session == null) return const SizedBox.shrink();

    final notifier = ref.read(locateProvider.notifier);
    final allVisible = session.hits.every((h) => h.visible);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 8, 8, 0),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  'Findings for "${session.query}" — ${session.hits.length} region(s)',
                  style: Theme.of(context).textTheme.titleSmall,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              TextButton.icon(
                onPressed: () => notifier.setAllVisible(!allVisible),
                icon: Icon(
                  allVisible ? Icons.visibility_off_outlined : Icons.visibility_outlined,
                  size: 16,
                ),
                label: Text(allVisible ? 'Hide all' : 'Show all'),
              ),
              IconButton(
                tooltip: 'Back to metrics',
                icon: const Icon(Icons.close, size: 18),
                onPressed: notifier.clear,
              ),
            ],
          ),
        ),
        const Divider(height: 8),
        Expanded(
          // Key on the query: a NEW search fully resets scroll position and
          // any expanded rows from the previous result list.
          child: ListView.builder(
            key: PageStorageKey('findings-${session.query}'),
            itemCount: session.hits.length,
            itemBuilder: (context, index) =>
                _FindingTile(index: index, state: session.hits[index],
                    selected: session.selected == index),
          ),
        ),
      ],
    );
  }
}

class _FindingTile extends ConsumerWidget {
  const _FindingTile({
    required this.index,
    required this.state,
    required this.selected,
  });

  final int index;
  final HitState state;
  final bool selected;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(locateProvider.notifier);
    final scheme = Theme.of(context).colorScheme;
    final hit = state.hit;

    return ExpansionTile(
      key: ValueKey('finding-${state.hit.label}-$index'),
      dense: true,
      initiallyExpanded: selected,
      onExpansionChanged: (open) => notifier.select(open ? index : null),
      backgroundColor: selected ? scheme.primaryContainer.withValues(alpha: 0.15) : null,
      leading: IconButton(
        tooltip: state.visible ? 'Hide box on canvas' : 'Show box on canvas',
        icon: Icon(
          state.visible ? Icons.visibility : Icons.visibility_off,
          size: 18,
          color: state.visible ? const Color(0xFFFFC107) : scheme.outline,
        ),
        onPressed: () => notifier.toggleVisible(index),
      ),
      title: Text(hit.label, style: const TextStyle(fontSize: 13)),
      subtitle: Text(
        state.analysis?.overviewLine ??
            '${hit.source} match · confidence ${(hit.confidence * 100).round()}%',
        style: TextStyle(fontSize: 11, color: scheme.outline),
      ),
      childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      expandedCrossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (state.analysis != null) ...[
          Text('Layers: ${state.analysis!.layers.join(", ")}',
              style: const TextStyle(fontSize: 12)),
          Text('Metrics: ${state.analysis!.metricsSummary}',
              style: const TextStyle(fontSize: 12)),
          if (state.analysis!.annotations.isNotEmpty)
            Text('Annotations: ${state.analysis!.annotations.take(6).join(" | ")}',
                style: const TextStyle(fontSize: 12)),
          const SizedBox(height: 8),
        ],
        if (state.description != null)
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: scheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Text(state.description!, style: const TextStyle(fontSize: 12)),
          )
        else
          Align(
            alignment: Alignment.centerLeft,
            child: state.describing
                ? const Padding(
                    padding: EdgeInsets.all(4),
                    child: SizedBox(
                      width: 16, height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : OutlinedButton.icon(
                    onPressed: () => notifier.describe(index),
                    icon: const Icon(Icons.auto_awesome, size: 14),
                    label: const Text('Describe (AI)', style: TextStyle(fontSize: 12)),
                  ),
          ),
      ],
    );
  }
}
