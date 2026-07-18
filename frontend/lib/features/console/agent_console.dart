import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/chat_provider.dart';

/// Right panel: chat with the compliance agent + quick-action macros.
class AgentConsole extends ConsumerStatefulWidget {
  const AgentConsole({super.key});

  @override
  ConsumerState<AgentConsole> createState() => _AgentConsoleState();
}

class _AgentConsoleState extends ConsumerState<AgentConsole> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();

  static const _macros = [
    'Verify VDE Compliance',
    'Check Bending Radii',
    'Generate Explanatory Report',
  ];

  void _send([String? text]) {
    final message = text ?? _controller.text;
    if (message.trim().isEmpty) return;
    _controller.clear();
    ref.read(chatProvider.notifier).send(message);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final messages = ref.watch(chatProvider);
    final scheme = Theme.of(context).colorScheme;

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Icon(Icons.smart_toy_outlined, color: scheme.primary),
              const SizedBox(width: 8),
              const Text('Compliance Agent'),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: ListView.builder(
            controller: _scrollController,
            padding: const EdgeInsets.all(12),
            itemCount: messages.length,
            itemBuilder: (context, index) {
              final msg = messages[index];
              final isUser = msg.role == 'user';
              return Align(
                alignment:
                    isUser ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(10),
                  constraints: const BoxConstraints(maxWidth: 300),
                  decoration: BoxDecoration(
                    color: isUser
                        ? scheme.primaryContainer
                        : scheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(msg.text, style: const TextStyle(fontSize: 13)),
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              for (final macro in _macros)
                ActionChip(
                  label: Text(macro, style: const TextStyle(fontSize: 12)),
                  onPressed: () => _send(macro),
                ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            controller: _controller,
            onSubmitted: (_) => _send(),
            decoration: InputDecoration(
              hintText: 'Ask about the plan…',
              border: const OutlineInputBorder(),
              isDense: true,
              suffixIcon: IconButton(
                icon: const Icon(Icons.send),
                onPressed: _send,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
