import 'package:flutter/material.dart';

import 'core/theme.dart';
import 'features/console/agent_console.dart';
import 'features/data_view/data_table_panel.dart';
import 'features/workspace/workspace_panel.dart';

class PlannerPlaygroundApp extends StatelessWidget {
  const PlannerPlaygroundApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "Rail50Hz.ai — Planner's Playground",
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      home: const PlannerDashboard(),
    );
  }
}

/// Three-panel workstation layout:
///  left/center: ingestion + canvas, bottom: data layer, right: agent console.
class PlannerDashboard extends StatelessWidget {
  const PlannerDashboard({super.key});

  void _showGuide(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Quick guide'),
        content: const SizedBox(
          width: 460,
          child: SingleChildScrollView(
            child: Text(
              '1. Upload a plan\n'
              '   Drop a .dwg or .dxf file on the canvas (or click to browse). '
              'The pipeline converts, extracts geometry, renders the plan and '
              'runs the compliance check automatically.\n\n'
              '2. Explore the canvas\n'
              '   Render = full-fidelity server image (all symbols) · '
              'Vectors = extracted data layer with semantic colors. '
              'Scroll/pinch to zoom, drag to pan, double-tap to reset. '
              'Use the layers icon to show/hide individual layers in both views.\n\n'
              '3. Talk to the Plan Copilot (right panel)\n'
              '   Ask compliance questions ("Check bending radii") or find '
              'components ("Wo ist der Schalthaus?") — found regions are '
              'highlighted as boxes on the canvas. Tap one of your earlier '
              'messages to edit & resend it; the history icon re-runs saved '
              'searches.\n\n'
              '4. Investigate findings (bottom panel)\n'
              '   After a search, each finding shows an instant overview. '
              'Toggle the eye to show/hide its box, expand a row to select it '
              '(orange on canvas), and click "Describe (AI)" for a detailed '
              'description — AI is only called when you ask.\n\n'
              '5. Sketch elements (draw mode)\n'
              '   Toggle the pencil icon, click points on the render, then '
              'tell the copilot e.g. "draw the cable line NYY-J between my '
              'points". The sketch is an overlay for discussion — the CAD '
              'file is never modified.\n\n'
              'Liability for final validation remains with the engineer.',
              style: TextStyle(fontSize: 13, height: 1.4),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Got it'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Rail50Hz.ai — Planner's Playground"),
        actions: [
          IconButton(
            tooltip: 'Quick guide',
            icon: const Icon(Icons.help_outline),
            onPressed: () => _showGuide(context),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            flex: 3,
            child: Column(
              children: const [
                Expanded(flex: 3, child: WorkspacePanel()),
                Divider(height: 1),
                Expanded(flex: 2, child: DataTablePanel()),
              ],
            ),
          ),
          const VerticalDivider(width: 1),
          const SizedBox(width: 380, child: AgentConsole()),
        ],
      ),
    );
  }
}
