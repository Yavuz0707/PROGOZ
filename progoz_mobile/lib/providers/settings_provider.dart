import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/api_config.dart';

class SettingsProvider extends ChangeNotifier {
  bool _fightNotifications = true;
  bool _plateNotifications = true;
  double _minScore = 50.0;
  String _serverUrl = kDefaultBaseUrl;

  bool get fightNotifications => _fightNotifications;
  bool get plateNotifications => _plateNotifications;
  double get minScore => _minScore;
  String get serverUrl => _serverUrl;

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _fightNotifications = prefs.getBool('fight_notifications') ?? true;
    _plateNotifications = prefs.getBool('plate_notifications') ?? true;
    _minScore = prefs.getDouble('min_score') ?? 50.0;
    final savedServerUrl = prefs.getString('server_url');
    _serverUrl = savedServerUrl ?? kDefaultBaseUrl;
    if (_serverUrl.contains('192.168.1.102') ||
        _serverUrl.contains('192.168.1.103')) {
      _serverUrl = kDefaultBaseUrl;
      await prefs.setString('server_url', _serverUrl);
    }
    notifyListeners();
  }

  Future<void> setFightNotifications(bool value) async {
    _fightNotifications = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('fight_notifications', value);
    notifyListeners();
  }

  Future<void> setPlateNotifications(bool value) async {
    _plateNotifications = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('plate_notifications', value);
    notifyListeners();
  }

  Future<void> setMinScore(double value) async {
    _minScore = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble('min_score', value);
    notifyListeners();
  }

  Future<void> setServerUrl(String value) async {
    _serverUrl = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_url', value);
    notifyListeners();
  }
}
