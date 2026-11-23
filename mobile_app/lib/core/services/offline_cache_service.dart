import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class CachedCatalogData {
  final Map<String, dynamic> config;
  final List<dynamic> categories;
  final List<dynamic> products;
  final DateTime cachedAt;

  CachedCatalogData({
    required this.config,
    required this.categories,
    required this.products,
    required this.cachedAt,
  });
}

class OfflineCacheService {
  static const String _keyConfig = 'cached_public_config';
  static const String _keyCategories = 'cached_categories';
  static const String _keyProducts = 'cached_products';
  static const String _keyTimestamp = 'cached_catalog_timestamp';

  final SharedPreferences _prefs;

  OfflineCacheService(this._prefs);

  Future<void> saveCatalogCache({
    required Map<String, dynamic> config,
    required List<dynamic> categories,
    required List<dynamic> products,
  }) async {
    await _prefs.setString(_keyConfig, jsonEncode(config));
    await _prefs.setString(_keyCategories, jsonEncode(categories));
    await _prefs.setString(_keyProducts, jsonEncode(products));
    await _prefs.setString(_keyTimestamp, DateTime.now().toIso8601String());
  }

  CachedCatalogData? getCachedCatalog() {
    final rawConfig = _prefs.getString(_keyConfig);
    final rawCategories = _prefs.getString(_keyCategories);
    final rawProducts = _prefs.getString(_keyProducts);
    final rawTime = _prefs.getString(_keyTimestamp);

    if (rawConfig == null || rawCategories == null || rawProducts == null) {
      return null;
    }

    try {
      final config = jsonDecode(rawConfig) as Map<String, dynamic>;
      final categories = jsonDecode(rawCategories) as List<dynamic>;
      final products = jsonDecode(rawProducts) as List<dynamic>;
      final time = rawTime != null ? DateTime.parse(rawTime) : DateTime.now();

      return CachedCatalogData(
        config: config,
        categories: categories,
        products: products,
        cachedAt: time,
      );
    } catch (_) {
      return null;
    }
  }

  bool get hasCache => _prefs.containsKey(_keyProducts);

  Future<void> clearCache() async {
    await _prefs.remove(_keyConfig);
    await _prefs.remove(_keyCategories);
    await _prefs.remove(_keyProducts);
    await _prefs.remove(_keyTimestamp);
  }
}
