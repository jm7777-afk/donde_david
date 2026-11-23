import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../core/services/api_service.dart';
import '../core/services/offline_cache_service.dart';
import '../core/services/storage_service.dart';
import '../models/categoria.dart';
import '../models/producto.dart';

class CatalogProvider extends ChangeNotifier {
  final ApiService _api;
  final StorageService _storage;
  final OfflineCacheService? _cache;

  List<Categoria> _categories = [];
  List<Producto> _products = [];
  Map<String, dynamic> _publicConfig = {};
  int? _selectedCategoryId;
  String _searchQuery = '';
  String? _activeTable;
  bool _isLoading = false;
  bool _isOffline = false;
  String? _errorMessage;

  List<Categoria> get categories => _categories;
  List<Producto> get products => _products;
  Map<String, dynamic> get publicConfig => _publicConfig;
  int? get selectedCategoryId => _selectedCategoryId;
  String get searchQuery => _searchQuery;
  String? get activeTable => _activeTable;
  bool get isLoading => _isLoading;
  bool get isOffline => _isOffline;
  String? get errorMessage => _errorMessage;

  double get tasaCambioBs {
    final raw = _publicConfig['tasa_cambio_bs'];
    if (raw == null) return 40.0; // fallback standard
    if (raw is num) return raw.toDouble();
    return double.tryParse(raw.toString()) ?? 40.0;
  }

  double get costoDelivery {
    final raw = _publicConfig['costo_delivery'];
    if (raw == null) return 5.0;
    if (raw is num) return raw.toDouble();
    return double.tryParse(raw.toString()) ?? 5.0;
  }

  double get costoEmpaque {
    final raw = _publicConfig['costo_empaque'];
    if (raw == null) return 1.0;
    if (raw is num) return raw.toDouble();
    return double.tryParse(raw.toString()) ?? 1.0;
  }

  double get impuestoPorcentaje {
    final raw = _publicConfig['impuesto_porcentaje'];
    if (raw == null) return 16.0;
    if (raw is num) return raw.toDouble();
    return double.tryParse(raw.toString()) ?? 16.0;
  }

  List<Producto> get filteredProducts {
    return _products.where((p) {
      if (!p.disponible) return false;
      if (_selectedCategoryId != null && p.categoriaId != _selectedCategoryId) {
        return false;
      }
      if (_searchQuery.isNotEmpty) {
        final query = _searchQuery.toLowerCase();
        final matchName = p.nombre.toLowerCase().contains(query);
        final matchDesc = p.descripcion.toLowerCase().contains(query);
        return matchName || matchDesc;
      }
      return true;
    }).toList();
  }

  List<Producto> get featuredProducts {
    return _products.where((p) => p.disponible).take(6).toList();
  }

  CatalogProvider(this._api, this._storage, [this._cache]) {
    _activeTable = _storage.getActiveTable();
    loadCatalog();
  }

  Future<void> loadCatalog() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      // 1. Configuraciones públicas
      Map<String, dynamic> fetchedConfig = {};
      try {
        final configRes = await _api.get(ApiConstants.configuracionesPublicas);
        if (configRes is Map<String, dynamic>) {
          fetchedConfig = configRes;
          _publicConfig = fetchedConfig;
        }
      } catch (_) {}

      // 2. Categorías
      List<dynamic> rawCats = [];
      final catRes = await _api.get(ApiConstants.categorias);
      if (catRes is List) {
        rawCats = catRes;
        _categories = catRes
            .whereType<Map<String, dynamic>>()
            .map((c) => Categoria.fromJson(c))
            .toList();
        _categories.sort((a, b) => a.orden.compareTo(b.orden));
      }

      // 3. Productos
      List<dynamic> rawProds = [];
      final prodRes = await _api.get(ApiConstants.productos);
      if (prodRes is List) {
        rawProds = prodRes;
        _products = prodRes
            .whereType<Map<String, dynamic>>()
            .map((p) => Producto.fromJson(p))
            .toList();
      }

      _isOffline = false;
      _isLoading = false;

      // Guardar en caché offline para disponibilidad sin conexión
      if (_cache != null && rawProds.isNotEmpty) {
        await _cache!.saveCatalogCache(
          config: _publicConfig,
          categories: rawCats,
          products: rawProds,
        );
      }

      notifyListeners();
    } catch (e) {
      // Intentar recuperación desde la caché offline
      if (_cache != null && _cache!.hasCache) {
        final cached = _cache!.getCachedCatalog();
        if (cached != null) {
          _publicConfig = cached.config;
          _categories = cached.categories
              .whereType<Map<String, dynamic>>()
              .map((c) => Categoria.fromJson(c))
              .toList();
          _categories.sort((a, b) => a.orden.compareTo(b.orden));
          _products = cached.products
              .whereType<Map<String, dynamic>>()
              .map((p) => Producto.fromJson(p))
              .toList();

          _isOffline = true;
          _isLoading = false;
          _errorMessage = 'Modo sin conexión: mostrando catálogo en caché';
          notifyListeners();
          return;
        }
      }

      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
    }
  }

  void selectCategory(int? categoryId) {
    _selectedCategoryId = categoryId;
    notifyListeners();
  }

  void setSearchQuery(String query) {
    _searchQuery = query.trim();
    notifyListeners();
  }

  Future<void> setActiveTable(String table) async {
    _activeTable = table;
    await _storage.setActiveTable(table);
    notifyListeners();
  }

  Future<void> clearActiveTable() async {
    _activeTable = null;
    await _storage.clearActiveTable();
    notifyListeners();
  }

  double convertToBs(double usdAmount) {
    return usdAmount * tasaCambioBs;
  }
}
