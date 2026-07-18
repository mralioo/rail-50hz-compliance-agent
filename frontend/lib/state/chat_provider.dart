import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../models/job.dart';
import 'pipeline_provider.dart';

class ChatMessage {
  const ChatMessage({required this.role, required this.text});

  final String role; // 'user' | 'agent'
  final String text;
}

class ChatNotifier extends Notifier<List<ChatMessage>> {
  @override
  List<ChatMessage> build() => const [
        ChatMessage(
          role: 'agent',
          text: 'Upload a DWG/DXF plan and I will check it against the active '
              'DB Ril / VDE guidelines. You can then ask follow-up questions.',
        ),
      ];

  bool _sending = false;

  Future<void> send(String message) async {
    final job = ref.read(pipelineProvider).job;
    if (_sending || message.trim().isEmpty) return;

    state = [...state, ChatMessage(role: 'user', text: message)];
    if (job == null || job.status != JobStatus.ready) {
      state = [
        ...state,
        const ChatMessage(
            role: 'agent', text: 'Process a plan first, then ask me again.'),
      ];
      return;
    }

    _sending = true;
    try {
      final reply = await ref.read(apiClientProvider).sendChat(job.id, message);
      state = [...state, ChatMessage(role: 'agent', text: reply)];
    } catch (e) {
      state = [...state, ChatMessage(role: 'agent', text: 'Agent error: $e')];
    } finally {
      _sending = false;
    }
  }
}

final chatProvider =
    NotifierProvider<ChatNotifier, List<ChatMessage>>(ChatNotifier.new);
