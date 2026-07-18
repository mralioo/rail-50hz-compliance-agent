import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:planner_playground/app.dart';

void main() {
  testWidgets('dashboard renders the three-panel layout', (tester) async {
    tester.view.physicalSize = const Size(1600, 1000);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(const ProviderScope(child: PlannerPlaygroundApp()));

    expect(find.text('Drop a .dwg / .dxf plan here'), findsOneWidget);
    expect(find.text('Compliance Agent'), findsOneWidget);
    expect(find.textContaining('Structured data layer'), findsOneWidget);
  });
}
