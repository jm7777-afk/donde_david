import 'dart:async';
import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../core/services/api_service.dart';
import '../core/services/websocket_service.dart';
import '../models/mesa.dart';
import '../models/pedido.dart';
import '../models/solicitud_mesa.dart';
import '../models/turno.dart';

class StaffProvider extends ChangeNotifier {
  final ApiService _api;
  final WebSocketService _ws;
  StreamSubscription<WebSocketEvent>? _wsSubscription;

  // Mesero
  List<Mesa> _mesas = [];
  List<SolicitudMesa> _solicitudes = [];
  List<Pedido> _pedidosListos = [];

  // Cocina KDS
  List<Pedido> _kitchenOrders = [];
  String? _kitchenFilterTipo;

  // Caja POS
  TurnoCaja? _turnoActivo;
  List<Pedido> _pendingCashierOrders = [];
  List<Pedido> _takeawayPickupOrders = [];
  List<Map<String, dynamic>> _movimientosCaja = [];

  // Delivery
  List<Pedido> _courierOrders = [];

  // Gerencia / Admin
  Map<String, dynamic>? _managerDashboard;
  List<dynamic> _adminProductos = [];
  List<dynamic> _adminCategorias = [];
  List<dynamic> _adminInsumos = [];
  List<dynamic> _adminMesas = [];
  List<dynamic> _adminUsuarios = [];
  Map<String, dynamic> _adminConfiguraciones = {};
  bool _adminLoading = false;

  bool _isLoading = false;
  String? _errorMessage;

  List<Mesa> get mesas => _mesas;
  List<SolicitudMesa> get solicitudes => _solicitudes;
  List<Pedido> get pedidosListos => _pedidosListos;

  List<Pedido> get kitchenOrders => _kitchenOrders;
  String? get kitchenFilterTipo => _kitchenFilterTipo;

  TurnoCaja? get turnoActivo => _turnoActivo;
  List<Pedido> get pendingCashierOrders => _pendingCashierOrders;
  List<Pedido> get takeawayPickupOrders => _takeawayPickupOrders;
  List<Map<String, dynamic>> get movimientosCaja => _movimientosCaja;

  List<Pedido> get courierOrders => _courierOrders;

  Map<String, dynamic>? get managerDashboard => _managerDashboard;
  List<dynamic> get adminProductos => _adminProductos;
  List<dynamic> get adminCategorias => _adminCategorias;
  List<dynamic> get adminInsumos => _adminInsumos;
  List<dynamic> get adminMesas => _adminMesas;
  List<dynamic> get adminUsuarios => _adminUsuarios;
  Map<String, dynamic> get adminConfiguraciones => _adminConfiguraciones;
  bool get adminLoading => _adminLoading;

  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  StaffProvider(this._api, this._ws) {
    _initWebSocketListener();
  }

  void _initWebSocketListener() {
    _wsSubscription = _ws.eventStream.listen((event) {
      // Whenever a staff event occurs, refresh state
      fetchMesas();
      fetchKitchenOrders();
      fetchCashierData();
      fetchCourierOrders();
    });
  }

  // ================= MESERO =================
  Future<void> fetchMesas() async {
    try {
      final res = await _api.get(ApiConstants.meseroMesas, requireAuth: true);
      if (res is List) {
        _mesas = res
            .whereType<Map<String, dynamic>>()
            .map((m) => Mesa.fromJson(m))
            .toList();
      }
      final solRes = await _api.get(
        ApiConstants.meseroSolicitudes,
        requireAuth: true,
      );
      if (solRes is List) {
        _solicitudes = solRes
            .whereType<Map<String, dynamic>>()
            .map((s) => SolicitudMesa.fromJson(s))
            .toList();
      }
      final readyRes = await _api.get(
        ApiConstants.meseroPedidosActivos,
        requireAuth: true,
      );
      if (readyRes is List) {
        _pedidosListos = readyRes
            .whereType<Map<String, dynamic>>()
            .map((p) => Pedido.fromJson(p))
            .toList();
      }
      notifyListeners();
    } catch (_) {}
  }

  Future<bool> actualizarLimpiezaMesa(int mesaId, String accion) async {
    try {
      await _api.put(
        '${ApiConstants.meseroLimpieza}/$mesaId/limpieza',
        body: {'accion': accion},
        requireAuth: true,
      );
      await fetchMesas();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> atenderSolicitudMesa(int solicitudId, String nuevoEstado) async {
    try {
      await _api.put(
        '${ApiConstants.meseroSolicitudes}/$solicitudId/estado',
        body: {'estado': nuevoEstado},
        requireAuth: true,
      );
      await fetchMesas();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> entregarPedidoMesa(int pedidoId) async {
    try {
      await _api.post(
        '${ApiConstants.meseroMarcarEntregado}/$pedidoId/marcar-entregado',
        requireAuth: true,
      );
      await fetchMesas();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  // ================= COCINA KDS =================
  Future<void> fetchKitchenOrders() async {
    try {
      final query = <String, dynamic>{};
      if (_kitchenFilterTipo != null) {
        query['tipo'] = _kitchenFilterTipo;
      }
      final res = await _api.get(
        ApiConstants.cocinaPedidos,
        queryParams: query,
        requireAuth: true,
      );
      if (res is List) {
        _kitchenOrders = res
            .whereType<Map<String, dynamic>>()
            .map((p) => Pedido.fromJson(p))
            .toList();
        notifyListeners();
      }
    } catch (_) {}
  }

  void setKitchenFilter(String? tipo) {
    _kitchenFilterTipo = tipo;
    fetchKitchenOrders();
  }

  Future<bool> actualizarEstadoCocina(int pedidoId, String nuevoEstado) async {
    try {
      await _api.put(
        '${ApiConstants.cocinaEstadoPedido}/$pedidoId/estado',
        queryParams: {'estado': nuevoEstado},
        requireAuth: true,
      );
      await fetchKitchenOrders();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  // ================= CAJA POS =================
  Future<void> fetchCashierData() async {
    try {
      // 1. Turno activo
      try {
        final turnoRes = await _api.get(
          ApiConstants.cajaTurnoActivo,
          requireAuth: true,
        );
        if (turnoRes is Map<String, dynamic>) {
          _turnoActivo = TurnoCaja.fromJson(turnoRes);
        }
      } catch (_) {
        _turnoActivo = null;
      }

      // 2. Pedidos pendientes
      final pendRes = await _api.get(
        ApiConstants.cajaPedidosPendientes,
        requireAuth: true,
      );
      if (pendRes is List) {
        _pendingCashierOrders = pendRes
            .whereType<Map<String, dynamic>>()
            .map((p) => Pedido.fromJson(p))
            .toList();
      }

      // 3. Pedidos para retiro
      final retiroRes = await _api.get(
        ApiConstants.cajaPedidosRetiro,
        requireAuth: true,
      );
      if (retiroRes is List) {
        _takeawayPickupOrders = retiroRes
            .whereType<Map<String, dynamic>>()
            .map((p) => Pedido.fromJson(p))
            .toList();
      }
      notifyListeners();
    } catch (_) {}
  }

  Future<bool> abrirTurnoCaja(double montoAperturaUsd) async {
    try {
      await _api.post(
        ApiConstants.cajaAbrirTurno,
        body: {'monto_apertura': montoAperturaUsd},
        requireAuth: true,
      );
      await fetchCashierData();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> cerrarTurnoCaja({
    required double efectivo,
    required double pagoMovil,
    required double puntoDeVenta,
  }) async {
    try {
      await _api.post(
        ApiConstants.cajaCerrarTurno,
        body: {
          'monto_cierre': efectivo,
          'arqueo': [
            {'metodo_pago': 'Efectivo', 'contado_usd': efectivo},
            {'metodo_pago': 'Pago Móvil', 'contado_usd': pagoMovil},
            {'metodo_pago': 'Punto de Venta', 'contado_usd': puntoDeVenta},
          ],
        },
        requireAuth: true,
      );
      await fetchCashierData();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> cobrarPedidoCaja({
    required int pedidoId,
    required String metodoPago,
    required String moneda,
    required double montoPagado,
  }) async {
    try {
      await _api.post(
        '${ApiConstants.cajaCobrar}/$pedidoId/cobrar',
        body: {
          'metodo_pago': metodoPago,
          'moneda_pago': moneda,
          'monto_recibido': montoPagado,
        },
        requireAuth: true,
      );
      await fetchCashierData();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> validarPagoMovilCaja(int pedidoId) async {
    try {
      await _api.post(
        '${ApiConstants.cajaConfirmarPago}/$pedidoId/confirmar-pago',
        body: {'aprobado': true},
        requireAuth: true,
      );
      await fetchCashierData();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> rechazarPagoMovilCaja(int pedidoId, String motivo) async {
    try {
      await _api.post(
        '${ApiConstants.cajaConfirmarPago}/$pedidoId/confirmar-pago',
        body: {'aprobado': false, 'observacion': motivo},
        requireAuth: true,
      );
      await fetchCashierData();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> confirmarRetiroLlevar(int pedidoId, String codigoRetiro) async {
    try {
      await _api.post(
        '${ApiConstants.cajaConfirmarRetiro}/$pedidoId/confirmar-retiro',
        body: {'codigo_retiro': codigoRetiro.trim()},
        requireAuth: true,
      );
      await fetchCashierData();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  // ================= DELIVERY REPARTIDOR =================
  Future<void> fetchCourierOrders() async {
    try {
      final res = await _api.get(
        ApiConstants.deliveryMisPedidos,
        requireAuth: true,
      );
      if (res is List) {
        _courierOrders = res
            .whereType<Map<String, dynamic>>()
            .map((p) => Pedido.fromJson(p))
            .toList();
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<bool> actualizarEstadoDelivery(
    int pedidoId,
    String nuevoEstado,
  ) async {
    try {
      await _api.post(
        '${ApiConstants.deliveryEstado}/$pedidoId/estado',
        body: {'estado': nuevoEstado},
        requireAuth: true,
      );
      await fetchCourierOrders();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> entregarDeliveryConOtp(int pedidoId, String otp) async {
    try {
      await _api.post(
        '${ApiConstants.deliveryEntregar}/$pedidoId/entregar',
        body: {'codigo_otp': otp.trim()},
        requireAuth: true,
      );
      await fetchCourierOrders();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> cambiarMesaPedido(int pedidoId, int nuevaMesa) async {
    try {
      await _api.post(
        '${ApiConstants.meseroCambiarMesa}/$pedidoId/cambiar-mesa',
        body: {'nueva_mesa': nuevaMesa},
        requireAuth: true,
      );
      await fetchMesas();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> crearYCobrarRapidoPos({
    required String numeroMesa,
    required String tipo,
    required String metodoPago,
    required String monedaPago,
    required double montoRecibido,
    required String nitCliente,
    required String nombreFactura,
    required List<Map<String, dynamic>> detalles,
  }) async {
    try {
      await _api.post(
        ApiConstants.cajaCrearYCobrarRapido,
        body: {
          'numero_mesa': numeroMesa,
          'tipo': tipo,
          'metodo_pago': metodoPago,
          'monto_recibido': montoRecibido,
          'moneda_pago': monedaPago,
          'nit_cliente': nitCliente.trim().isEmpty ? 'CF' : nitCliente.trim(),
          'nombre_factura': nombreFactura.trim().isEmpty
              ? 'Consumidor Final'
              : nombreFactura.trim(),
          'detalles': detalles,
        },
        requireAuth: true,
      );
      await fetchCashierData();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<void> fetchMovimientosCaja() async {
    try {
      final res = await _api.get(
        ApiConstants.cajaMovimientos,
        requireAuth: true,
      );
      if (res is List) {
        _movimientosCaja = res.whereType<Map<String, dynamic>>().toList();
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<bool> registrarMovimientoCaja({
    required String concepto,
    required double montoUsd,
    required String metodoPago,
    String? observacion,
  }) async {
    try {
      await _api.post(
        ApiConstants.cajaMovimientos,
        body: {
          'concepto': concepto,
          'monto_usd': montoUsd,
          'metodo_pago': metodoPago,
          if (observacion != null && observacion.isNotEmpty)
            'observacion': observacion,
        },
        requireAuth: true,
      );
      await fetchMovimientosCaja();
      await fetchCashierData();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> actualizarUbicacionRepartidor(
    int pedidoId,
    double lat,
    double lng,
  ) async {
    try {
      await _api.post(
        '${ApiConstants.deliveryUbicacion}/$pedidoId/ubicacion',
        body: {'lat': lat, 'lng': lng},
        requireAuth: true,
      );
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<void> fetchManagerDashboard() async {
    try {
      final res = await _api.get(
        ApiConstants.gerenciaDashboard,
        requireAuth: true,
      );
      if (res is Map<String, dynamic>) {
        _managerDashboard = res;
        notifyListeners();
      }
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  // ================= ADMIN: PRODUCTOS =================
  Future<void> fetchAdminProductos() async {
    _adminLoading = true;
    notifyListeners();
    try {
      final res = await _api.get(
        ApiConstants.adminProductos,
        requireAuth: true,
      );
      if (res is List) {
        _adminProductos = res;
      }
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _adminLoading = false;
      notifyListeners();
    }
  }

  Future<bool> crearProductoAdmin(Map<String, dynamic> data) async {
    try {
      await _api.post(
        ApiConstants.adminProductos,
        body: data,
        requireAuth: true,
      );
      await fetchAdminProductos();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> actualizarProductoAdmin(
    int id,
    Map<String, dynamic> data,
  ) async {
    try {
      await _api.put(
        '${ApiConstants.adminProductos}/$id',
        body: data,
        requireAuth: true,
      );
      await fetchAdminProductos();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> eliminarProductoAdmin(int id) async {
    try {
      await _api.delete(
        '${ApiConstants.adminProductos}/$id',
        requireAuth: true,
      );
      await fetchAdminProductos();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> toggleProductoDisponibilidad(int id, bool actual) async {
    try {
      await _api.put(
        '${ApiConstants.adminProductos}/$id',
        body: {'disponible': !actual},
        requireAuth: true,
      );
      final idx = _adminProductos.indexWhere((p) => p['id'] == id);
      if (idx != -1) {
        _adminProductos[idx]['disponible'] = !actual;
      }
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  // ================= ADMIN: CATEGORIAS =================
  Future<void> fetchAdminCategorias() async {
    _adminLoading = true;
    notifyListeners();
    try {
      final res = await _api.get(
        ApiConstants.adminCategorias,
        requireAuth: true,
      );
      if (res is List) {
        _adminCategorias = res;
      }
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _adminLoading = false;
      notifyListeners();
    }
  }

  Future<bool> crearCategoriaAdmin(
    String nombre,
    String? descripcion, {
    String? imagenUrl,
  }) async {
    try {
      await _api.post(
        ApiConstants.adminCategorias,
        body: {
          'nombre': nombre,
          'descripcion': descripcion ?? '',
          'imagen_url': imagenUrl ?? '',
          'orden': 0,
        },
        requireAuth: true,
      );
      await fetchAdminCategorias();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> eliminarCategoriaAdmin(int id) async {
    try {
      await _api.delete(
        '${ApiConstants.adminCategorias}/$id',
        requireAuth: true,
      );
      await fetchAdminCategorias();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  // ================= ADMIN: INSUMOS =================
  Future<void> fetchAdminInsumos() async {
    _adminLoading = true;
    notifyListeners();
    try {
      final res = await _api.get(ApiConstants.adminInsumos, requireAuth: true);
      if (res is List) {
        _adminInsumos = res;
      }
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _adminLoading = false;
      notifyListeners();
    }
  }

  Future<bool> crearInsumoAdmin({
    required String nombre,
    required double stock,
    required double stockMinimo,
    required String unidad,
  }) async {
    try {
      await _api.post(
        ApiConstants.adminInsumos,
        body: {
          'nombre': nombre,
          'stock_actual': stock,
          'stock_minimo': stockMinimo,
          'unidad_medida': unidad,
        },
        requireAuth: true,
      );
      await fetchAdminInsumos();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> registrarIngresoInsumoAdmin({
    required int insumoId,
    required double cantidad,
    required double costoTotal,
    String? proveedor,
  }) async {
    try {
      await _api.post(
        '${ApiConstants.adminInsumos}/$insumoId/ingreso',
        body: {
          'cantidad': cantidad,
          'costo_total': costoTotal,
          'proveedor': proveedor ?? 'Compra General',
        },
        requireAuth: true,
      );
      await fetchAdminInsumos();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  // ================= ADMIN: MESAS =================
  Future<void> fetchAdminMesas() async {
    _adminLoading = true;
    notifyListeners();
    try {
      final res = await _api.get(ApiConstants.adminMesas, requireAuth: true);
      if (res is List) {
        _adminMesas = res;
      }
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _adminLoading = false;
      notifyListeners();
    }
  }

  Future<bool> crearMesaAdmin({
    required int numeroMesa,
    int capacidad = 4,
  }) async {
    try {
      await _api.post(
        ApiConstants.adminMesas,
        body: {'numero_mesa': numeroMesa, 'capacidad': capacidad},
        requireAuth: true,
      );
      await fetchAdminMesas();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> eliminarMesaAdmin(int numeroMesa) async {
    try {
      await _api.delete(
        '${ApiConstants.adminMesas}/$numeroMesa',
        requireAuth: true,
      );
      await fetchAdminMesas();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  // ================= ADMIN: USUARIOS =================
  Future<void> fetchAdminUsuarios() async {
    _adminLoading = true;
    notifyListeners();
    try {
      final res = await _api.get(ApiConstants.adminUsuarios, requireAuth: true);
      if (res is List) {
        _adminUsuarios = res;
      }
    } catch (e) {
      _errorMessage = e.toString();
    } finally {
      _adminLoading = false;
      notifyListeners();
    }
  }

  Future<bool> crearUsuarioAdmin(Map<String, dynamic> data) async {
    try {
      await _api.post(
        ApiConstants.adminUsuarios,
        body: data,
        requireAuth: true,
      );
      await fetchAdminUsuarios();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> actualizarUsuarioAdmin(int id, Map<String, dynamic> data) async {
    try {
      await _api.put(
        '${ApiConstants.adminUsuarios}/$id',
        body: data,
        requireAuth: true,
      );
      await fetchAdminUsuarios();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  // ================= ADMIN: CONFIGURACIONES =================
  Future<void> fetchAdminConfiguraciones() async {
    try {
      final res = await _api.get(ApiConstants.configuracionesPublicas);
      if (res is Map<String, dynamic>) {
        _adminConfiguraciones = res;
        notifyListeners();
      }
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
    }
  }

  Future<bool> guardarConfiguracionesLote(Map<String, String> configs) async {
    try {
      await _api.post(
        ApiConstants.adminConfiguracionesLote,
        body: {'configuraciones': configs},
        requireAuth: true,
      );
      await fetchAdminConfiguraciones();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> actualizarTasaBcvManual(double tasa) async {
    try {
      await _api.post(
        ApiConstants.adminConfiguraciones,
        body: {'clave': 'tasa_cambio_bs', 'valor': tasa.toStringAsFixed(2)},
        requireAuth: true,
      );
      await fetchAdminConfiguraciones();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> sincronizarTasaBcvOficial() async {
    try {
      await _api.post(ApiConstants.adminTasaBcvActualizar, requireAuth: true);
      await fetchAdminConfiguraciones();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  @override
  void dispose() {
    _wsSubscription?.cancel();
    super.dispose();
  }
}
