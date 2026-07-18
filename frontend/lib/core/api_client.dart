import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/job.dart';
import 'config.dart';

/// Thin typed wrapper over the FastAPI gateway (`backend/app/api/routes.py`).
class ApiClient {
  ApiClient([Dio? dio])
      : _dio = dio ?? Dio(BaseOptions(baseUrl: AppConfig.apiBaseUrl));

  final Dio _dio;

  Future<Job> uploadFile(String path, String filename) async {
    final form = FormData.fromMap({
      'file': await MultipartFile.fromFile(path, filename: filename),
    });
    final response = await _dio.post('/api/v1/jobs', data: form);
    return Job.fromJson(response.data as Map<String, dynamic>);
  }

  Future<Job> getJob(String jobId) async {
    final response = await _dio.get('/api/v1/jobs/$jobId');
    return Job.fromJson(response.data as Map<String, dynamic>);
  }

  Future<String> sendChat(String jobId, String message) async {
    final response = await _dio.post(
      '/api/v1/jobs/$jobId/chat',
      data: {'message': message},
    );
    return (response.data as Map<String, dynamic>)['reply'] as String;
  }
}

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());
