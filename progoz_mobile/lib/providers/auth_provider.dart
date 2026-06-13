import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/auth_service.dart';
import '../services/api_service.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

class AuthProvider extends ChangeNotifier {
  final _authService = AuthService();
  AuthStatus _status = AuthStatus.unknown;
  String? _error;
  bool _loading = false;

  AuthStatus get status => _status;
  String? get error => _error;
  bool get loading => _loading;

  Future<void> checkAuth() async {
    final loggedIn = await _authService.isLoggedIn();
    _status = loggedIn ? AuthStatus.authenticated : AuthStatus.unauthenticated;
    notifyListeners();
  }

  Future<bool> login(String username, String password) async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      await _authService.login(username, password);
      _status = AuthStatus.authenticated;
      _loading = false;
      notifyListeners();
      _registerFcmToken();
      return true;
    } catch (e) {
      final raw = e.toString().replaceFirst('Exception: ', '');
      if (raw.contains('Failed to fetch') || raw.contains('XMLHttpRequest') || raw.contains('ClientException')) {
        _error = 'Sunucuya bağlanılamadı.\nWeb tarayıcısında CORS hatası oluştu.\nLütfen uygulamayı mobil cihazda deneyin.';
      } else {
        _error = raw;
      }
      _loading = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> logout() async {
    await _authService.logout();
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }

  Future<void> _registerFcmToken() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final fcmToken = prefs.getString('fcm_token');
      final userId = prefs.getString('user_id');
      if (fcmToken != null && userId != null && userId.isNotEmpty) {
        await ApiService().subscribeNotifications(userId, fcmToken);
      }
    } catch (_) {}
  }
}
