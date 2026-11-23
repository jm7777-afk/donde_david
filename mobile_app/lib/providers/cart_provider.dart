import 'package:flutter/material.dart';
import '../models/producto.dart';

class CartItem {
  final Producto product;
  int quantity;
  final List<ProductoExtra> selectedExtras;
  final List<String> sinIngredientes;
  final String? nota;

  CartItem({
    required this.product,
    this.quantity = 1,
    this.selectedExtras = const [],
    this.sinIngredientes = const [],
    this.nota,
  });

  double get unitPrice {
    double base = product.precio;
    for (var extra in selectedExtras) {
      base += extra.precio;
    }
    return base;
  }

  double get subtotal => unitPrice * quantity;

  Map<String, dynamic> toCustomizationsMap() {
    final map = <String, dynamic>{};
    if (selectedExtras.isNotEmpty) {
      map['extras'] = selectedExtras.map((e) => e.nombre).toList();
    }
    if (sinIngredientes.isNotEmpty) {
      for (var sin in sinIngredientes) {
        map['sin_${sin.toLowerCase().replaceAll(' ', '_')}'] = true;
      }
    }
    if (nota != null && nota!.isNotEmpty) {
      map['nota'] = nota;
    }
    return map;
  }

  Map<String, dynamic> toOrderDetailJson() {
    return {
      'producto_id': product.id,
      'cantidad': quantity,
      'personalizaciones': toCustomizationsMap(),
    };
  }
}

class CartProvider extends ChangeNotifier {
  final List<CartItem> _items = [];

  // Checkout delivery configuration
  String _orderType = 'mesa'; // mesa, delivery, llevar
  String _paymentMode = 'PAGAR_ANTES'; // PAGAR_ANTES, PAGAR_DESPUES
  String _paymentMethod = 'Efectivo'; // Efectivo, Punto de Venta, Pago Móvil
  String _paymentCurrency = 'VES'; // VES, USD
  String _paymentReference = '';

  // Delivery details
  String _deliveryNombre = '';
  String _deliveryTelefono = '';
  String _deliveryDireccion = '';
  double? _deliveryLat;
  double? _deliveryLng;

  List<CartItem> get items => _items;
  int get itemCount => _items.fold(0, (sum, i) => sum + i.quantity);
  bool get isEmpty => _items.isEmpty;

  String get orderType => _orderType;
  String get paymentMode => _paymentMode;
  String get paymentMethod => _paymentMethod;
  String get paymentCurrency => _paymentCurrency;
  String get paymentReference => _paymentReference;

  String get deliveryNombre => _deliveryNombre;
  String get deliveryTelefono => _deliveryTelefono;
  String get deliveryDireccion => _deliveryDireccion;
  double? get deliveryLat => _deliveryLat;
  double? get deliveryLng => _deliveryLng;

  double get subtotal => _items.fold(0.0, (sum, i) => sum + i.subtotal);

  double calculateTax(double taxPercent) => subtotal * (taxPercent / 100.0);

  double calculateDeliveryFee(double deliveryCost) =>
      _orderType == 'delivery' ? deliveryCost : 0.0;

  double calculateEmpaqueFee(double empaqueCost) =>
      _orderType == 'llevar' ? empaqueCost : 0.0;

  double calculateTotal({
    required double taxPercent,
    required double deliveryCost,
    required double empaqueCost,
  }) {
    return subtotal +
        calculateTax(taxPercent) +
        calculateDeliveryFee(deliveryCost) +
        calculateEmpaqueFee(empaqueCost);
  }

  int get estimatedPoints => (subtotal * 10).toInt();

  void addItem({
    required Producto product,
    int quantity = 1,
    List<ProductoExtra> selectedExtras = const [],
    List<String> sinIngredientes = const [],
    String? nota,
  }) {
    // Check if identical item already in cart
    final index = _items.indexWhere((item) {
      if (item.product.id != product.id) return false;
      if (item.selectedExtras.length != selectedExtras.length) return false;
      if (item.sinIngredientes.length != sinIngredientes.length) return false;
      if (item.nota != nota) return false;
      return true;
    });

    if (index >= 0) {
      _items[index].quantity += quantity;
    } else {
      _items.add(
        CartItem(
          product: product,
          quantity: quantity,
          selectedExtras: List.from(selectedExtras),
          sinIngredientes: List.from(sinIngredientes),
          nota: nota,
        ),
      );
    }
    notifyListeners();
  }

  void incrementQuantity(int index) {
    if (index >= 0 && index < _items.length) {
      _items[index].quantity++;
      notifyListeners();
    }
  }

  void decrementQuantity(int index) {
    if (index >= 0 && index < _items.length) {
      if (_items[index].quantity > 1) {
        _items[index].quantity--;
      } else {
        _items.removeAt(index);
      }
      notifyListeners();
    }
  }

  void removeItem(int index) {
    if (index >= 0 && index < _items.length) {
      _items.removeAt(index);
      notifyListeners();
    }
  }

  void clearCart() {
    _items.clear();
    _paymentReference = '';
    notifyListeners();
  }

  void setOrderType(String type) {
    _orderType = type;
    if (_orderType != 'mesa') {
      _paymentMode = 'PAGAR_ANTES';
    }
    notifyListeners();
  }

  void setPaymentMode(String mode) {
    _paymentMode = mode;
    notifyListeners();
  }

  void setPaymentMethod(String method) {
    _paymentMethod = method;
    notifyListeners();
  }

  void setPaymentCurrency(String currency) {
    _paymentCurrency = currency;
    notifyListeners();
  }

  void setPaymentReference(String ref) {
    _paymentReference = ref.trim();
    notifyListeners();
  }

  void setDeliveryDetails({
    required String nombre,
    required String telefono,
    required String direccion,
    double? lat,
    double? lng,
  }) {
    _deliveryNombre = nombre.trim();
    _deliveryTelefono = telefono.trim();
    _deliveryDireccion = direccion.trim();
    _deliveryLat = lat;
    _deliveryLng = lng;
    notifyListeners();
  }
}
