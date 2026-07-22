import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/locate_provider.dart';
import '../../state/pipeline_provider.dart';
import 'findings_panel.dart';

/// Bottom panel: processed metadata (areas, run lengths, annotated
/// parameters). When the locator agent has results, it switches to the
/// findings deep-dive view instead.
class DataTablePanel extends ConsumerWidget {
  const DataTablePanel({super.key});

  static const _labels = {
    'room_area': 'Room area',
    'run_length': 'Cabling run length',
    'cable_bending_radius': 'Cable bending radius',
    'cable_pulling_force': 'Cable pulling force',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final payload = ref.watch(pipelineProvider).job?.payload;

    if (ref.watch(locateProvider) != null) {
      return const FindingsPanel();
    }

    if (payload == null) {
      return const Center(
        child: Text('Structured data layer — process a plan to populate'),
      );
    }

    return SingleChildScrollView(
      scrollDirection: Axis.vertical,
      child: SizedBox(
        width: double.infinity,
        child: DataTable(
          headingTextStyle: Theme.of(context).textTheme.titleSmall,
          columns: const [
            DataColumn(label: Text('Parameter')),
            DataColumn(label: Text('Layer')),
            DataColumn(label: Text('Value'), numeric: true),
            DataColumn(label: Text('Unit')),
          ],
          rows: [
            for (final metric in payload.metrics)
              DataRow(cells: [
                DataCell(Text(_labels[metric.name] ?? metric.name)),
                DataCell(Text(metric.layer ?? '—')),
                DataCell(Text(metric.value.toStringAsFixed(2))),
                DataCell(Text(metric.unit)),
              ]),
          ],
        ),
      ),
    );
  }
}
