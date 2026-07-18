import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api_client.dart';
import '../models/job.dart';
import 'locate_provider.dart';
import 'pipeline_provider.dart';

/// Queries like "where is …" / "wo ist …" are visual-grounding requests and
/// are routed to the locator agent instead of the plain chat agent.
final _locateIntent = RegExp(
  r'\b(where|wo\b|locate|zeig|zeige|markiere|highlight|show me|find the|finde)\b',
  caseSensitive: false,
);

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
          text: 'Hi, I am your Plan Copilot. Upload a DWG/DXF plan and I will '
              'check it against the active DB Ril / VDE guidelines. Then ask '
              'me anything about it — or find components with "where is …" / '
              '"wo ist …" and I will highlight them on the canvas.',
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
      if (_locateIntent.hasMatch(message) && await _tryLocate(job.id, message)) {
        return;
      }
      final reply = await ref.read(apiClientProvider).sendChat(job.id, message);
      state = [...state, ChatMessage(role: 'agent', text: reply)];
    } catch (e) {
      state = [...state, ChatMessage(role: 'agent', text: 'Agent error: $e')];
    } finally {
      _sending = false;
    }
  }

  /// Returns true when the locator produced hits (query fully handled);
  /// false lets the message fall through to the normal chat agent.
  Future<bool> _tryLocate(String jobId, String message) async {
    final result = await ref.read(apiClientProvider).locate(jobId, message);
    if (result.hits.isEmpty) return false;

    ref.read(locateProvider.notifier).show(result);
    final labels = result.hits.take(4).map((h) => '- ${h.label}').join('\n');
    state = [
      ...state,
      ChatMessage(
        role: 'agent',
        text: 'Found ${result.hits.length} matching region(s) — highlighted '
            'on the plan canvas:\n$labels',
      ),
    ];
    return true;
  }
}

final chatProvider =
    NotifierProvider<ChatNotifier, List<ChatMessage>>(ChatNotifier.new);
