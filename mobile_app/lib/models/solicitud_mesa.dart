class SolicitudMesa {
  final int id;
  final int mesaId;
  final String numeroMesa;
  final String tipo; // LLAMAR_MESERO, SOLICITAR_CUENTA
  final String estado; // PENDIENTE, ATENDIDA, CANCELADA
  final String? nota;
  final DateTime? fechaCreacion;

  SolicitudMesa({
    required this.id,
    required this.mesaId,
    required this.numeroMesa,
    required this.tipo,
    required this.estado,
    this.nota,
    this.fechaCreacion,
  });

  bool get isPending => estado == 'PENDIENTE';
  bool get isCallWaiter => tipo == 'LLAMAR_MESERO';
  bool get isRequestBill => tipo == 'SOLICITAR_CUENTA';

  factory SolicitudMesa.fromJson(Map<String, dynamic> json) {
    DateTime? fecha;
    if (json['fecha_creacion'] != null) {
      fecha = DateTime.tryParse(json['fecha_creacion'].toString());
    }

    return SolicitudMesa(
      id: json['id'] is int
          ? json['id']
          : int.tryParse(json['id']?.toString() ?? '0') ?? 0,
      mesaId: json['mesa_id'] is int
          ? json['mesa_id']
          : int.tryParse(json['mesa_id']?.toString() ?? '0') ?? 0,
      numeroMesa: json['numero_mesa']?.toString() ?? 'Mesa',
      tipo: json['tipo']?.toString() ?? 'LLAMAR_MESERO',
      estado: json['estado']?.toString() ?? 'PENDIENTE',
      nota: json['nota']?.toString(),
      fechaCreacion: fecha,
    );
  }
}
