import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../core/config.dart';
import '../models/job.dart';

/// Drives the upload -> poll -> ready lifecycle shown in the status bar.
class PipelineState {
  const PipelineState({this.job, this.uploading = false, this.error});

  final Job? job;
  final bool uploading;
  final String? error;

  bool get busy =>
      uploading ||
      (job != null &&
          job!.status != JobStatus.ready &&
          job!.status != JobStatus.failed);
}

class PipelineNotifier extends Notifier<PipelineState> {
  Timer? _pollTimer;

  @override
  PipelineState build() {
    ref.onDispose(() => _pollTimer?.cancel());
    return const PipelineState();
  }

  Future<void> processFile(String path, String filename) async {
    _pollTimer?.cancel();
    state = const PipelineState(uploading: true);
    try {
      final job = await ref.read(apiClientProvider).uploadFile(path, filename);
      state = PipelineState(job: job);
      _startPolling(job.id);
    } catch (e) {
      state = PipelineState(error: 'Upload failed: $e');
    }
  }

  void _startPolling(String jobId) {
    _pollTimer = Timer.periodic(AppConfig.pollInterval, (timer) async {
      try {
        final job = await ref.read(apiClientProvider).getJob(jobId);
        state = PipelineState(job: job);
        if (job.status == JobStatus.ready || job.status == JobStatus.failed) {
          timer.cancel();
        }
      } catch (e) {
        timer.cancel();
        state = PipelineState(job: state.job, error: 'Polling failed: $e');
      }
    });
  }

  void reset() {
    _pollTimer?.cancel();
    state = const PipelineState();
  }
}

final pipelineProvider =
    NotifierProvider<PipelineNotifier, PipelineState>(PipelineNotifier.new);
