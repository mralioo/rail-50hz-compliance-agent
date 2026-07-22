import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/draft.dart';
import '../models/job.dart';
import '../models/locate.dart';
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

  Future<LocateResult> locate(String jobId, String query) async {
    final response = await _dio.post(
      '/api/v1/jobs/$jobId/locate',
      data: {'query': query},
    );
    return LocateResult.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<HitAnalysis>> analyzeHits(String jobId, List<LocateHit> hits) async {
    final response = await _dio.post(
      '/api/v1/jobs/$jobId/hits/analyze',
      data: {'hits': [for (final h in hits) h.toJson()]},
    );
    return [
      for (final a in (response.data as Map<String, dynamic>)['analyses'] as List)
        HitAnalysis.fromJson(a as Map<String, dynamic>),
    ];
  }

  Future<String> describeHit(String jobId, LocateHit hit) async {
    final response = await _dio.post(
      '/api/v1/jobs/$jobId/hits/describe',
      data: {'hit': hit.toJson()},
    );
    return (response.data as Map<String, dynamic>)['description'] as String;
  }

  Future<String> sendChat(String jobId, String message) async {
    final response = await _dio.post(
      '/api/v1/jobs/$jobId/chat',
      data: {'message': message},
    );
    return (response.data as Map<String, dynamic>)['reply'] as String;
  }

  /// Render pixel size [w, h] for aspect-true canvas overlays.
  Future<List<int>> renderMeta(String jobId) async {
    final response = await _dio.get('/api/v1/jobs/$jobId/render/meta');
    return ((response.data as Map<String, dynamic>)['px'] as List)
        .map((v) => v as int)
        .toList();
  }

  /// Draftsman agent: connect clicked points into a sketch element.
  Future<(DrawnElement, String)> draw(
      String jobId, String instruction, List<List<double>> pointsImage) async {
    final response = await _dio.post(
      '/api/v1/jobs/$jobId/draw',
      data: {'instruction': instruction, 'points_image': pointsImage},
    );
    final data = response.data as Map<String, dynamic>;
    return (
      DrawnElement.fromJson(data['element'] as Map<String, dynamic>),
      data['reply'] as String,
    );
  }

  /// Recent locator searches (server-side history, newest first).
  Future<List<SearchRecord>> searchHistory({int limit = 20}) async {
    final response = await _dio.get('/api/v1/searches',
        queryParameters: {'limit': limit});
    return [
      for (final r in response.data as List)
        SearchRecord.fromJson(r as Map<String, dynamic>),
    ];
  }
}

class SearchRecord {
  const SearchRecord({
    required this.query,
    required this.filename,
    required this.hitCount,
  });

  final String query;
  final String filename;
  final int hitCount;

  factory SearchRecord.fromJson(Map<String, dynamic> json) => SearchRecord(
        query: json['query'] as String,
        filename: json['filename'] as String,
        hitCount: json['hit_count'] as int,
      );
}

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());
