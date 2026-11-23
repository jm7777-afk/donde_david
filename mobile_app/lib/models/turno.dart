class TurnoCaja {
  final int id;
  final int usuarioId;
  final String estado; // ABIERTO, CERRADO
  final double montoAperturaUsd;
  final double efectivoEsperado;
  final DateTime? fechaApertura;

  TurnoCaja({
    required this.id,
    required this.usuarioId,
    required this.estado,
    required this.montoAperturaUsd,
    this.efectivoEsperado = 0.0,
    this.fechaApertura,
  });

  bool get isOpen => estado == 'ABIERTO';

  factory TurnoCaja.fromJson(Map<String, dynamic> json) {
    DateTime? fecha;
    if (json['fecha_apertura'] != null) {
      fecha = DateTime.tryParse(json['fecha_apertura'].toString());
    }

    return TurnoCaja(
      id: json['id'] is int
          ? json['id']
          : int.tryParse(json['id']?.toString() ?? '0') ?? 0,
      usuarioId: json['usuario_id'] is int
          ? json['usuario_id']
          : int.tryParse(json['usuario_id']?.toString() ?? '0') ?? 0,
      estado: json['estado']?.toString() ?? 'CERRADO',
      montoAperturaUsd:
          (json['monto_apertura_usd'] is num
              ? (json['monto_apertura_usd'] as num).toDouble()
              : double.tryParse(
                  json['monto_apertura_usd']?.toString() ?? '0.0',
                )) ??
          0.0,
      efectivoEsperado:
          (json['efectivo_esperado'] is num
              ? (json['efectivo_esperado'] as num).toDouble()
              : double.tryParse(
                  json['efectivo_esperado']?.toString() ?? '0.0',
                )) ??
          0.0,
      fechaApertura: fecha,
    );
  }
}
