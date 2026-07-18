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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Rail50Hz.ai — Planner's Playground"),
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
