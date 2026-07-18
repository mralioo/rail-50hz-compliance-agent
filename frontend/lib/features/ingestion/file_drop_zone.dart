import 'package:desktop_drop/desktop_drop.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/pipeline_provider.dart';

/// Dashed-border drop area: click-to-pick or drag-and-drop, .dwg/.dxf only.
class FileDropZone extends ConsumerStatefulWidget {
  const FileDropZone({super.key});

  @override
  ConsumerState<FileDropZone> createState() => _FileDropZoneState();
}

class _FileDropZoneState extends ConsumerState<FileDropZone> {
  bool _hovering = false;

  bool _isCadFile(String name) {
    final lower = name.toLowerCase();
    return lower.endsWith('.dwg') || lower.endsWith('.dxf');
  }

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['dwg', 'dxf'],
    );
    final file = result?.files.single;
    if (file?.path != null && mounted) {
      ref.read(pipelineProvider.notifier).processFile(file!.path!, file.name);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return DropTarget(
      onDragEntered: (_) => setState(() => _hovering = true),
      onDragExited: (_) => setState(() => _hovering = false),
      onDragDone: (details) {
        setState(() => _hovering = false);
        final file = details.files.where((f) => _isCadFile(f.name)).firstOrNull;
        if (file != null) {
          ref.read(pipelineProvider.notifier).processFile(file.path, file.name);
        }
      },
      child: InkWell(
        onTap: _pickFile,
        child: Container(
          decoration: BoxDecoration(
            border: Border.all(
              color: _hovering ? scheme.primary : scheme.outline,
              width: 2,
              style: BorderStyle.solid,
            ),
            borderRadius: BorderRadius.circular(12),
            color: _hovering ? scheme.primary.withValues(alpha: 0.08) : null,
          ),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.upload_file, size: 56, color: scheme.primary),
                const SizedBox(height: 12),
                const Text('Drop a .dwg / .dxf plan here'),
                const SizedBox(height: 4),
                Text('or click to browse',
                    style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
