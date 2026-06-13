import 'package:flutter/material.dart';
import '../models/plate.dart';
import '../services/api_service.dart';

class PlatesProvider extends ChangeNotifier {
  final _api = ApiService();
  List<Plate> _plates = [];
  bool _loading = false;
  String? _error;

  List<Plate> get plates => _plates;
  bool get loading => _loading;
  String? get error => _error;

  Future<void> load() async {
    _loading = true;
    _error = null;
    notifyListeners();

    try {
      _plates = await _api.getPlates();
    } on UnauthorizedException {
      _error = 'unauthorized';
    } catch (e) {
      _error = 'Plakalar yüklenemedi';
    }

    _loading = false;
    notifyListeners();
  }
}
