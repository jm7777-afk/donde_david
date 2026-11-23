class Mesa {
  final int id;
  final int numeroMesa;
  final String estado; // LIBRE, OCUPADA, PENDIENTE_LIMPIEZA, EN_LIMPIEZA
  final int capacidad;
  final String? clienteActual;
  final int tiempoOcupacionMin;
  final int pedidosActivos;
  final int solicitudesPendientes;

  Mesa({
    required this.id,
    required this.numeroMesa,
    required this.estado,
    this.capacidad = 4,
    this.clienteActual,
    this.tiempoOcupacionMin = 0,
    this.pedidosActivos = 0,
    this.solicitudesPendientes = 0,
  });

  bool get isFree => estado == 'LIBRE';
  bool get isOccupied => estado == 'OCUPADA';
  bool get isPendingCleaning => estado == 'PENDIENTE_LIMPIEZA';
  bool get isCleaning => estado == 'EN_LIMPIEZA';

  String get displayName => 'Mesa #$numeroMesa';

  factory Mesa.fromJson(Map<String, dynamic> json) {
    return Mesa(
      id: json['id'] is int
          ? json['id']
          : int.tryParse(json['id']?.toString() ?? '0') ?? 0,
      numeroMesa: json['numero_mesa'] is int
          ? json['numero_mesa']
          : int.tryParse(json['numero_mesa']?.toString() ?? '0') ?? 0,
      estado: json['estado']?.toString() ?? 'LIBRE',
      capacidad: json['capacidad'] is int
          ? json['capacidad']
          : int.tryParse(json['capacidad']?.toString() ?? '4') ?? 4,
      clienteActual: json['cliente_actual']?.toString(),
      tiempoOcupacionMin: json['tiempo_ocupacion_min'] is int
          ? json['tiempo_ocupacion_min']
          : int.tryParse(json['tiempo_ocupacion_min']?.toString() ?? '0') ?? 0,
      pedidosActivos: json['pedidos_activos'] is int
          ? json['pedidos_activos']
          : int.tryParse(json['pedidos_activos']?.toString() ?? '0') ?? 0,
      solicitudesPendientes: json['solicitudes_pendientes'] is int
          ? json['solicitudes_pendientes']
          : int.tryParse(json['solicitudes_pendientes']?.toString() ?? '0') ??
                0,
    );
  }
}
