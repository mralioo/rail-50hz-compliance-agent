import 'package:flutter/material.dart';

ThemeData buildAppTheme() {
  return ThemeData(
    useMaterial3: true,
    colorSchemeSeed: const Color(0xFF1A5FB4),
    brightness: Brightness.dark,
    visualDensity: VisualDensity.compact,
  );
}
