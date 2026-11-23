import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../constants/api_constants.dart';

class StorageService {
  static StorageService? _instance;
  static SharedPreferences? _prefs;

  SharedPreferences? get prefs => _prefs;

  static const String _keyToken = 'donde_david_token';
  static const String _keyUser = 'donde_david_user';
  static const String _keyBaseUrl = 'donde_david_base_url';
  static const String _keyActiveTable = 'donde_david_active_table';

  static Future<StorageService> getInstance() async {
    if (_instance == null) {
      _prefs = await SharedPreferences.getInstance();
      _instance = StorageService();
    }
    return _instance!;
  }

  // Token
  String? getToken() => _prefs?.getString(_keyToken);
  Future<bool> setToken(String token) async =>
      await _prefs?.setString(_keyToken, token) ?? false;
  Future<bool> removeToken() async => await _prefs?.remove(_keyToken) ?? false;

  // Base URL
  String getBaseUrl() {
    final saved = _prefs?.getString(_keyBaseUrl);
    if (saved != null && saved.isNotEmpty) return saved;
    return ApiConstants.defaultProductionUrl;
  }

  Future<bool> setBaseUrl(String url) async {
    var cleaned = url.trim();
    if (cleaned.endsWith('/')) {
      cleaned = cleaned.substring(0, cleaned.length - 1);
    }
    return await _prefs?.setString(_keyBaseUrl, cleaned) ?? false;
  }

  // User Profile
  Map<String, dynamic>? getUser() {
    final raw = _prefs?.getString(_keyUser);
    if (raw == null) return null;
    try {
      return jsonDecode(raw) as Map<String, dynamic>;
    } catch (_) {
      return null;
    }
  }

  Future<bool> setUser(Map<String, dynamic> userMap) async {
    return await _prefs?.setString(_keyUser, jsonEncode(userMap)) ?? false;
  }

  Future<bool> removeUser() async => await _prefs?.remove(_keyUser) ?? false;

  // Active Table (QR)
  String? getActiveTable() => _prefs?.getString(_keyActiveTable);
  Future<bool> setActiveTable(String table) async =>
      await _prefs?.setString(_keyActiveTable, table) ?? false;
  Future<bool> clearActiveTable() async =>
      await _prefs?.remove(_keyActiveTable) ?? false;

  // Clear Session
  Future<void> clearAuth() async {
    await removeToken();
    await removeUser();
  }
}
