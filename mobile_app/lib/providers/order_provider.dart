import 'package:flutter/material.dart';
import '../core/constants/api_constants.dart';
import '../core/services/api_service.dart';
import '../models/pedido.dart';
import 'cart_provider.dart';

class OrderProvider extends ChangeNotifier {
  final ApiService _api;

  Pedido? _currentTrackedOrder;
  List<Pedido> _orderHistory = [];
  bool _isSubmitting = false;
  bool _isLoadingHistory = false;
  String? _errorMessage;

  Pedido? get currentTrackedOrder => _currentTrackedOrder;
  List<Pedido> get orderHistory => _orderHistory;
  bool get isSubmitting => _isSubmitting;
  bool get isLoadingHistory => _isLoadingHistory;
  String? get errorMessage => _errorMessage;

  OrderProvider(this._api);

  Future<Pedido?> submitOrder({
    required CartProvider cart,
    required String tableNumber,
  }) async {
    if (cart.isEmpty) {
      _errorMessage = 'El carrito está vacío';
      notifyListeners();
      return null;
    }

    _isSubmitting = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final detailsPayload = cart.items
          .map((i) => i.toOrderDetailJson())
          .toList();

      final payload = <String, dynamic>{
        'tipo': cart.orderType,
        'numero_mesa': cart.orderType == 'mesa' ? tableNumber : 'Mostrador',
        'detalles': detailsPayload,
        'modo_pago': cart.paymentMode,
      };

      if (cart.paymentMode == 'PAGAR_ANTES') {
        payload['metodo_pago'] = cart.paymentMethod;
        payload['moneda_pago'] = cart.paymentCurrency;
        if (cart.paymentMethod == 'Pago Móvil') {
          payload['referencia_pago'] = cart.paymentReference;
        }
      }

      if (cart.orderType == 'delivery') {
        payload['nombre_cliente_delivery'] = cart.deliveryNombre;
        payload['telefono_delivery'] = cart.deliveryTelefono;
        payload['direccion_delivery'] = cart.deliveryDireccion;
        if (cart.deliveryLat != null && cart.deliveryLng != null) {
          payload['delivery_lat'] = cart.deliveryLat;
          payload['delivery_lng'] = cart.deliveryLng;
        }
      }

      final res = await _api.post(
        ApiConstants.crearPedido,
        body: payload,
        requireAuth: true,
      );

      if (res is Map<String, dynamic>) {
        final order = Pedido.fromJson(res);
        _currentTrackedOrder = order;
        _orderHistory.insert(0, order);
        cart.clearCart();
        _isSubmitting = false;
        notifyListeners();
        return order;
      }
      throw ApiException('Respuesta de orden no válida');
    } catch (e) {
      _errorMessage = e.toString();
      _isSubmitting = false;
      notifyListeners();
      return null;
    }
  }

  Future<void> refreshTrackedOrder([int? orderId]) async {
    final idToRefresh = orderId ?? _currentTrackedOrder?.id;
    if (idToRefresh == null) return;

    try {
      final res = await _api.get(
        '${ApiConstants.trackingPedido}/$idToRefresh/seguimiento',
        requireAuth: true,
      );
      if (res is Map<String, dynamic>) {
        _currentTrackedOrder = Pedido.fromJson(res);
        notifyListeners();
      }
    } catch (_) {}
  }

  Future<void> fetchOrderHistory() async {
    _isLoadingHistory = true;
    notifyListeners();

    try {
      final res = await _api.get(
        ApiConstants.historialPedidos,
        requireAuth: true,
      );
      if (res is List) {
        _orderHistory = res
            .whereType<Map<String, dynamic>>()
            .map((p) => Pedido.fromJson(p))
            .toList();
      }
      _isLoadingHistory = false;
      notifyListeners();
    } catch (e) {
      _isLoadingHistory = false;
      notifyListeners();
    }
  }

  Future<bool> sendTableServiceRequest({
    required String tableNumber,
    required String tipo, // LLAMAR_MESERO, SOLICITAR_CUENTA
    String? nota,
  }) async {
    try {
      final int mesaNum =
          int.tryParse(tableNumber.replaceAll(RegExp(r'[^0-9]'), '')) ?? 1;
      await _api.post(
        ApiConstants.solicitudesMesa,
        body: {
          'numero_mesa': mesaNum,
          'tipo': tipo,
          if (nota != null && nota.isNotEmpty) 'nota': nota,
        },
        requireAuth: true,
      );
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<bool> submitServiceReview({
    required String clientName,
    required int rating,
    required String comment,
  }) async {
    try {
      await _api.post(
        ApiConstants.resenas,
        body: {
          'nombre_cliente': clientName,
          'estrellas': rating,
          'comentario': comment,
        },
      );
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      notifyListeners();
      return false;
    }
  }

  void setTrackedOrder(Pedido order) {
    _currentTrackedOrder = order;
    notifyListeners();
  }
}
