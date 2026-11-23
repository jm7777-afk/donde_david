import 'dart:convert';

class DetallePedido {
  final int? id;
  final int productoId;
  final String productoNombre;
  final int cantidad;
  final double precioUnitario;
  final double subtotal;
  final Map<String, dynamic> personalizaciones;
  final String estado;
  final String? observaciones;

  DetallePedido({
    this.id,
    required this.productoId,
    required this.productoNombre,
    required this.cantidad,
    required this.precioUnitario,
    required this.subtotal,
    this.personalizaciones = const {},
    this.estado = 'PENDIENTE',
    this.observaciones,
  });

  factory DetallePedido.fromJson(Map<String, dynamic> json) {
    Map<String, dynamic> pers = {};
    final rawPers = json['personalizaciones'];
    if (rawPers != null) {
      if (rawPers is Map<String, dynamic>) {
        pers = rawPers;
      } else if (rawPers is String && rawPers.isNotEmpty) {
        try {
          pers = jsonDecode(rawPers);
        } catch (_) {}
      }
    }

    String pNombre = json['producto_nombre']?.toString() ?? '';
    if (pNombre.isEmpty && json['producto'] is Map) {
      pNombre = json['producto']['nombre']?.toString() ?? '';
    }

    return DetallePedido(
      id: json['id'] is int
          ? json['id']
          : int.tryParse(json['id']?.toString() ?? ''),
      productoId: json['producto_id'] is int
          ? json['producto_id']
          : int.tryParse(json['producto_id']?.toString() ?? '0') ?? 0,
      productoNombre: pNombre.isNotEmpty
          ? pNombre
          : 'Producto #${json['producto_id']}',
      cantidad: json['cantidad'] is int
          ? json['cantidad']
          : int.tryParse(json['cantidad']?.toString() ?? '1') ?? 1,
      precioUnitario:
          (json['precio_unitario'] is num
              ? (json['precio_unitario'] as num).toDouble()
              : double.tryParse(
                  json['precio_unitario']?.toString() ?? '0.0',
                )) ??
          0.0,
      subtotal:
          (json['subtotal'] is num
              ? (json['subtotal'] as num).toDouble()
              : double.tryParse(json['subtotal']?.toString() ?? '0.0')) ??
          0.0,
      personalizaciones: pers,
      estado: json['estado']?.toString() ?? 'PENDIENTE',
      observaciones: json['observaciones']?.toString(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'producto_id': productoId,
      'cantidad': cantidad,
      'personalizaciones': personalizaciones,
    };
  }
}

class Pedido {
  final int id;
  final String numeroMesa;
  final String tipo; // mesa, llevar, delivery
  final String
  estado; // PENDIENTE, COBRADO, EN_PREPARACION, LISTO, ENTREGADO, CANCELADO
  final String estadoPago; // PENDIENTE, PAGADO, PENDIENTE_VALIDACION, CANCELADO
  final String modoPago; // PAGAR_ANTES, PAGAR_DESPUES
  final String? metodoPago; // Efectivo, Punto de Venta, Pago Móvil
  final String? monedaPago; // USD, VES
  final double total;
  final List<DetallePedido> detalles;
  final DateTime? fechaCreacion;
  final String? codigoRetiro; // Para pedidos "llevar"
  final String? otpEntrega; // Para pedidos "delivery"
  final String? deliveryNombre;
  final String? deliveryTelefono;
  final String? deliveryDireccion;
  final double? deliveryLat;
  final double? deliveryLng;
  final int? repartidorId;
  final String?
  estadoDelivery; // NO_ASIGNADO, ASIGNADO, RECOGIDO, EN_CAMINO, ENTREGADO

  Pedido({
    required this.id,
    required this.numeroMesa,
    required this.tipo,
    required this.estado,
    required this.estadoPago,
    this.modoPago = 'PAGAR_ANTES',
    this.metodoPago,
    this.monedaPago,
    required this.total,
    this.detalles = const [],
    this.fechaCreacion,
    this.codigoRetiro,
    this.otpEntrega,
    this.deliveryNombre,
    this.deliveryTelefono,
    this.deliveryDireccion,
    this.deliveryLat,
    this.deliveryLng,
    this.repartidorId,
    this.estadoDelivery,
  });

  bool get isPaid => estadoPago == 'PAGADO';
  bool get isTakeaway => tipo == 'llevar';
  bool get isDelivery => tipo == 'delivery';
  bool get isDineIn => tipo == 'mesa';

  factory Pedido.fromJson(Map<String, dynamic> json) {
    List<DetallePedido> detallesList = [];
    if (json['detalles'] is List) {
      detallesList = (json['detalles'] as List)
          .whereType<Map<String, dynamic>>()
          .map((d) => DetallePedido.fromJson(d))
          .toList();
    }

    DateTime? fecha;
    if (json['fecha_creacion'] != null) {
      fecha = DateTime.tryParse(json['fecha_creacion'].toString());
    }

    return Pedido(
      id: json['id'] is int
          ? json['id']
          : int.tryParse(json['id']?.toString() ?? '0') ?? 0,
      numeroMesa: json['numero_mesa']?.toString() ?? 'Mostrador',
      tipo: json['tipo']?.toString() ?? 'mesa',
      estado: json['estado']?.toString() ?? 'PENDIENTE',
      estadoPago: json['estado_pago']?.toString() ?? 'PENDIENTE',
      modoPago: json['modo_pago']?.toString() ?? 'PAGAR_ANTES',
      metodoPago: json['metodo_pago']?.toString(),
      monedaPago: json['moneda_pago']?.toString() ?? 'USD',
      total:
          (json['total'] is num
              ? (json['total'] as num).toDouble()
              : double.tryParse(json['total']?.toString() ?? '0.0')) ??
          0.0,
      detalles: detallesList,
      fechaCreacion: fecha,
      codigoRetiro: json['codigo_retiro']?.toString(),
      otpEntrega: json['otp_entrega']?.toString() ?? json['otp']?.toString(),
      deliveryNombre: json['delivery_nombre']?.toString(),
      deliveryTelefono: json['delivery_telefono']?.toString(),
      deliveryDireccion: json['delivery_direccion']?.toString(),
      deliveryLat: json['delivery_lat'] != null
          ? double.tryParse(json['delivery_lat'].toString())
          : null,
      deliveryLng: json['delivery_lng'] != null
          ? double.tryParse(json['delivery_lng'].toString())
          : null,
      repartidorId: json['repartidor_id'] != null
          ? int.tryParse(json['repartidor_id'].toString())
          : null,
      estadoDelivery: json['estado_delivery']?.toString(),
    );
  }
}
