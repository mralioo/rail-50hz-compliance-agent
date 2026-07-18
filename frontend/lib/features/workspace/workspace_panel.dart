import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/job.dart';
import '../../state/pipeline_provider.dart';
import '../canvas/plan_canvas.dart';
import '../ingestion/file_drop_zone.dart';
import '../ingestion/pipeline_status_bar.dart';

/// Left/center panel: drop zone (no file yet) or canvas (payload available),
/// with the pipeline status bar always visible on top.
class WorkspacePanel extends ConsumerWidget {
  const WorkspacePanel({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pipeline = ref.watch(pipelineProvider);
    final payload = pipeline.job?.payload;

    return Column(
      children: [
        const PipelineStatusBar(),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: payload != null
                ? PlanCanvas(payload: payload)
                : const FileDropZone(),
          ),
        ),
        if (pipeline.job?.status == JobStatus.failed)
          Padding(
            padding: const EdgeInsets.all(8),
            child: Text(
              pipeline.job?.error ?? 'Pipeline failed',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ),
      ],
    );
  }
}
