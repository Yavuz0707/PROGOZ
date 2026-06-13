import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config/api_config.dart';

class AuthService {
  static const _tokenKey = 'auth_token';
  static const _userIdKey = 'user_id';
  static const _usernameKey = 'username';

  Future<String> _apiUrl() async {
    final prefs = await SharedPreferences.getInstance();
    final base = prefs.getString('server_url') ?? kDefaultBaseUrl;
    return '$base/api';
  }

  Future<Map<String, dynamic>> login(String username, String password) async {
    final apiUrl = await _apiUrl();
    final response = await http.post(
      Uri.parse('$apiUrl/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );

    if (response.statusCode == 200) {
      final body = jsonDecode(response.body) as Map<String, dynamic>;
      final data = (body['data'] ?? body) as Map<String, dynamic>;
      final user = data['user'] as Map<String, dynamic>?;
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_tokenKey, data['access_token']?.toString() ?? '');
      await prefs.setString(_userIdKey, user?['id']?.toString() ?? '');
      await prefs.setString(_usernameKey, username);
      return data;
    } else {
      String message;
      try {
        final error = jsonDecode(response.body) as Map<String, dynamic>;
        message = error['detail']?.toString() ??
            error['message']?.toString() ??
            response.body;
      } catch (_) {
        message = response.body.isNotEmpty ? response.body : 'Giriş başarısız (${response.statusCode})';
      }
      throw Exception(message);
    }
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    await prefs.remove(_userIdKey);
    await prefs.remove(_usernameKey);
  }

  Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_tokenKey);
  }

  Future<String?> getUserId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_userIdKey);
  }

  Future<String?> getUsername() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_usernameKey);
  }

  Future<bool> isLoggedIn() async {
    final token = await getToken();
    return token != null && token.isNotEmpty;
  }
}
