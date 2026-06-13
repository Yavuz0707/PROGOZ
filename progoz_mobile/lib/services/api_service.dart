import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config/api_config.dart';
import '../models/incident.dart';
import '../models/plate.dart';

class UnauthorizedException implements Exception {}

class ApiService {
  Future<String> _apiUrl() async {
    final prefs = await SharedPreferences.getInstance();
    final base = prefs.getString('server_url') ?? kDefaultBaseUrl;
    return '$base/api';
  }

  Future<Map<String, String>> _authHeaders() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('auth_token') ?? '';
    return {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $token',
    };
  }

  Future<List<Incident>> getIncidents({
    int limit = 50,
    String? sourceName,
    String? level,
  }) async {
    final apiUrl = await _apiUrl();
    final headers = await _authHeaders();
    final params = <String, String>{'limit': '$limit'};
    if (level != null && level.isNotEmpty) params['severity'] = level;
    final uri = Uri.parse('$apiUrl/incidents').replace(queryParameters: params);
    final response = await http.get(uri, headers: headers);

    if (response.statusCode == 200) {
      final body = jsonDecode(response.body);
      final List data = (body is Map ? (body['data'] ?? body['items'] ?? []) : body) as List;
      var incidents =
          data.map((j) => Incident.fromJson(j as Map<String, dynamic>)).toList();
      if (sourceName != null && sourceName.isNotEmpty) {
        incidents = incidents.where((i) => i.sourceName == sourceName).toList();
      }
      return incidents;
    } else if (response.statusCode == 401) {
      throw UnauthorizedException();
    } else {
      throw Exception('${response.statusCode}: ${response.body}');
    }
  }

  /// Mevcut olaylardan benzersiz kaynak adlarını ve olay sayılarını çıkarır.
  Future<Map<String, int>> getIncidentSources() async {
    final incidents = await getIncidents(limit: 500);
    final counts = <String, int>{};
    for (final i in incidents) {
      counts[i.sourceName] = (counts[i.sourceName] ?? 0) + 1;
    }
    return counts;
  }

  Future<void> confirmIncident(String id) async {
    final apiUrl = await _apiUrl();
    final headers = await _authHeaders();
    final response = await http.post(
      Uri.parse('$apiUrl/incidents/$id/confirm'),
      headers: headers,
    );
    if (response.statusCode == 401) throw UnauthorizedException();
    if (response.statusCode >= 400) throw Exception('İşlem başarısız');
  }

  Future<void> dismissIncident(String id) async {
    final apiUrl = await _apiUrl();
    final headers = await _authHeaders();
    final response = await http.post(
      Uri.parse('$apiUrl/incidents/$id/dismiss'),
      headers: headers,
    );
    if (response.statusCode == 401) throw UnauthorizedException();
    if (response.statusCode >= 400) throw Exception('İşlem başarısız');
  }

  Future<List<Plate>> getPlates({int limit = 100, String? sourceName}) async {
    final apiUrl = await _apiUrl();
    final headers = await _authHeaders();
    final params = <String, String>{'limit': '$limit'};
    final uri = Uri.parse('$apiUrl/plates').replace(queryParameters: params);
    final response = await http.get(uri, headers: headers);

    if (response.statusCode == 200) {
      final body = jsonDecode(response.body);
      final List data = (body is Map ? (body['data'] ?? body['items'] ?? []) : body) as List;
      var plates =
          data.map((j) => Plate.fromJson(j as Map<String, dynamic>)).toList();
      if (sourceName != null && sourceName.isNotEmpty) {
        plates = plates.where((p) => p.sourceName == sourceName).toList();
      }
      return plates;
    } else if (response.statusCode == 401) {
      throw UnauthorizedException();
    } else {
      throw Exception('${response.statusCode}: ${response.body}');
    }
  }

  /// Mevcut plakalardan benzersiz kaynak adlarını ve plaka sayılarını çıkarır.
  Future<Map<String, int>> getPlateSources() async {
    final plates = await getPlates(limit: 500);
    final counts = <String, int>{};
    for (final p in plates) {
      counts[p.sourceName] = (counts[p.sourceName] ?? 0) + 1;
    }
    return counts;
  }

  Future<void> subscribeNotifications(String userId, String fcmToken) async {
    final apiUrl = await _apiUrl();
    final headers = await _authHeaders();
    await http.post(
      Uri.parse('$apiUrl/notifications/subscribe'),
      headers: headers,
      body: jsonEncode({'user_id': userId, 'fcm_token': fcmToken}),
    );
  }
}
