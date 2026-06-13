import 'package:flutter/material.dart';
import '../models/incident.dart';
import '../services/api_service.dart';

class IncidentsProvider extends ChangeNotifier {
  final _api = ApiService();
  List<Incident> _incidents = [];
  bool _loading = false;
  String? _error;

  List<Incident> get incidents => _incidents;
  bool get loading => _loading;
  String? get error => _error;

  int get unreadCount => _incidents.where((i) => !i.isRead).length;

  int get todayCount {
    final today = DateTime.now();
    return _incidents.where((i) {
      return i.startTime.year == today.year &&
          i.startTime.month == today.month &&
          i.startTime.day == today.day;
    }).length;
  }

  DateTime? get lastEventTime =>
      _incidents.isEmpty ? null : _incidents.first.startTime;

  Future<void> load() async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      _incidents = await _api.getIncidents();
    } on UnauthorizedException {
      _error = 'unauthorized';
    } catch (e) {
      _error = e.toString().replaceFirst('Exception: ', '');
    }

    _loading = false;
    notifyListeners();
  }

  void markAsRead(String id) {
    final index = _incidents.indexWhere((i) => i.id == id);
    if (index != -1) {
      _incidents[index].isRead = true;
      notifyListeners();
    }
  }

  Future<void> confirmIncident(String id) async {
    await _api.confirmIncident(id);
    await load();
  }

  Future<void> dismissIncident(String id) async {
    await _api.dismissIncident(id);
    await load();
  }

  void addIncidentFromNotification(Map<String, dynamic> data) {
    try {
      final incident = Incident.fromJson(data);
      _incidents.insert(0, incident);
      notifyListeners();
    } catch (_) {
      load();
    }
  }
}
