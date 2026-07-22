import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api_client.dart';
import '../../state/chat_provider.dart';

/// Right panel: Plan Copilot — the conversational interface to the uploaded
/// plan (compliance questions, component search, explanations).
/// UX: all text is selectable; tapping one of your earlier queries loads it
/// back into the input for editing; the history icon re-runs saved searches.
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
    'Where is the Schalthaus?',
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

  void _editQuery(String text) {
    _controller.text = text;
    _controller.selection =
        TextSelection.collapsed(offset: _controller.text.length);
  }

  Future<void> _showHistory() async {
    final List<SearchRecord> records;
    try {
      records = await ref.read(apiClientProvider).searchHistory();
    } catch (_) {
      return;
    }
    if (!mounted || records.isEmpty) return;
    showModalBottomSheet<void>(
      context: context,
      builder: (context) => ListView(
        padding: const EdgeInsets.all(8),
        children: [
          Padding(
            padding: const EdgeInsets.all(8),
            child: Text('Search history',
                style: Theme.of(context).textTheme.titleSmall),
          ),
          for (final r in records)
            ListTile(
              dense: true,
              leading: const Icon(Icons.history, size: 18),
              title: Text(r.query, style: const TextStyle(fontSize: 13)),
              subtitle: Text('${r.filename} · ${r.hitCount} hit(s)',
                  style: const TextStyle(fontSize: 11)),
              onTap: () {
                Navigator.pop(context);
                _send(r.query);
              },
            ),
        ],
      ),
    );
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
          padding: const EdgeInsets.fromLTRB(12, 12, 4, 12),
          child: Row(
            children: [
              Icon(Icons.smart_toy_outlined, color: scheme.primary),
              const SizedBox(width: 8),
              const Expanded(child: Text('Plan Copilot')),
              IconButton(
                tooltip: 'Search history',
                icon: const Icon(Icons.history, size: 20),
                onPressed: _showHistory,
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: SelectionArea(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(12),
              itemCount: messages.length,
              itemBuilder: (context, index) {
                final msg = messages[index];
                final isUser = msg.role == 'user';
                final bubble = Container(
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
                );
                return Align(
                  alignment:
                      isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: isUser
                      ? Tooltip(
                          message: 'Tap to edit & resend',
                          waitDuration: const Duration(milliseconds: 600),
                          child: InkWell(
                            onTap: () => _editQuery(msg.text),
                            borderRadius: BorderRadius.circular(10),
                            child: bubble,
                          ),
                        )
                      : bubble,
                );
              },
            ),
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
              hintText: 'Ask about the plan, or "where is …?"',
              helperText: 'Tip: "wo ist der Kabelkanal" highlights regions',
              helperStyle: const TextStyle(fontSize: 10),
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
