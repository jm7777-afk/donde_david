import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../core/services/api_service.dart';
import '../core/services/storage_service.dart';
import '../core/services/websocket_service.dart';
import '../models/usuario.dart';

class AuthProvider extends ChangeNotifier {
  final ApiService _api;
  final StorageService _storage;
  final WebSocketService _ws;

  Usuario? _user;
  String? _token;
  bool _isLoading = false;
  String? _errorMessage;

  Usuario? get user => _user;
  String? get token => _token;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get isAuthenticated => _token != null && _token!.isNotEmpty;
  bool get isStaff => _user != null && _user!.isStaff;

  AuthProvider(this._api, this._storage, this._ws) {
    _loadStoredSession();
  }

  void _loadStoredSession() {
    _token = _storage.getToken();
    final userMap = _storage.getUser();
    if (userMap != null) {
      _user = Usuario.fromJson(userMap);
      if (_user!.isStaff) {
        _ws.connect();
      }
    }
    notifyListeners();
  }

  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final res = await _api.post(
        ApiConstants.login,
        body: {'nombre_usuario': username.trim(), 'password': password},
      );

      if (res is Map<String, dynamic> && res.containsKey('access_token')) {
        _token = res['access_token'];
        await _storage.setToken(_token!);

        if (res['usuario'] is Map<String, dynamic>) {
          _user = Usuario.fromJson(res['usuario']);
          await _storage.setUser(res['usuario']);
        }

        if (_user != null && _user!.isStaff) {
          _ws.connect();
        }

        _isLoading = false;
        notifyListeners();
        return true;
      }
      throw ApiException('Respuesta de autenticación inválida');
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> register({
    required String nombre,
    required String apellido,
    required String email,
    required String telefono,
    required String username,
    required String password,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final res = await _api.post(
        ApiConstants.register,
        body: {
          'nombre': nombre.trim(),
          'apellido': apellido.trim(),
          'email': email.trim(),
          'telefono': telefono.trim(),
          'nombre_usuario': username.trim(),
          'password': password,
        },
      );

      if (res is Map<String, dynamic> && res.containsKey('access_token')) {
        _token = res['access_token'];
        await _storage.setToken(_token!);

        if (res['usuario'] is Map<String, dynamic>) {
          _user = Usuario.fromJson(res['usuario']);
          await _storage.setUser(res['usuario']);
        }

        _isLoading = false;
        notifyListeners();
        return true;
      }
      throw ApiException('Registro no completado');
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> refreshProfile() async {
    if (!isAuthenticated) return;
    try {
      final res = await _api.get(ApiConstants.me, requireAuth: true);
      if (res is Map<String, dynamic>) {
        _user = Usuario.fromJson(res);
        await _storage.setUser(res);
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> logout() async {
    _user = null;
    _token = null;
    await _storage.clearAuth();
    _ws.disconnect();
    notifyListeners();
  }
}
