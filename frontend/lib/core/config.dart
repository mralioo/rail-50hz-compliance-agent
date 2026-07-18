/// Backend endpoint configuration.
///
/// Override at build/run time:
///   flutter run -d linux --dart-define=API_BASE_URL=https://my-cloud-run-url
class AppConfig {
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  /// Poll interval for job status while the pipeline is running.
  static const pollInterval = Duration(seconds: 1);
}
