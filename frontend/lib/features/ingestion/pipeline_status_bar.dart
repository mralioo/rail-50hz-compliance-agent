import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/job.dart';
import '../../state/pipeline_provider.dart';

/// Idle -> Uploading -> Converting -> Extracting -> Analyzing -> Ready.
class PipelineStatusBar extends ConsumerWidget {
  const PipelineStatusBar({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final pipeline = ref.watch(pipelineProvider);
    final job = pipeline.job;

    final String label;
    if (pipeline.uploading) {
      label = 'Uploading…';
    } else if (pipeline.error != null) {
      label = pipeline.error!;
    } else if (job == null) {
      label = 'Idle — waiting for a plan';
    } else {
      label = '${job.filename} — ${job.status.label}';
    }

    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        child: Row(
          children: [
            if (pipeline.busy)
              const SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              )
            else
              Icon(
                job?.status == JobStatus.failed
                    ? Icons.error_outline
                    : job?.status == JobStatus.ready
                        ? Icons.check_circle_outline
                        : Icons.radio_button_unchecked,
                size: 18,
              ),
            const SizedBox(width: 12),
            Expanded(child: Text(label, overflow: TextOverflow.ellipsis)),
            if (job != null)
              TextButton(
                onPressed: () => ref.read(pipelineProvider.notifier).reset(),
                child: const Text('New plan'),
              ),
          ],
        ),
      ),
    );
  }
}
