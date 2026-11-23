class Usuario {
  final int id;
  final String nombre;
  final String apellido;
  final String nombreUsuario;
  final String? email;
  final String? telefono;
  final String rol;
  final int puntosFidelidad;
  final int pedidosCount;
  final double totalGastado;

  Usuario({
    required this.id,
    required this.nombre,
    required this.apellido,
    required this.nombreUsuario,
    this.email,
    this.telefono,
    required this.rol,
    this.puntosFidelidad = 0,
    this.pedidosCount = 0,
    this.totalGastado = 0.0,
  });

  String get nombreCompleto => '$nombre $apellido'.trim();

  bool get isStaff => [
    'admin',
    'supervisor',
    'gerente',
    'caja',
    'cocina',
    'mesero',
    'repartidor',
  ].contains(rol);
  bool get isClient => rol == 'cliente';
  bool get isAdmin => rol == 'admin' || rol == 'supervisor';
  bool get isKitchen => rol == 'cocina';
  bool get isCashier => rol == 'caja';
  bool get isWaiter => rol == 'mesero';
  bool get isCourier => rol == 'repartidor';

  factory Usuario.fromJson(Map<String, dynamic> json) {
    return Usuario(
      id: json['id'] is int
          ? json['id']
          : int.tryParse(json['id']?.toString() ?? '0') ?? 0,
      nombre: json['nombre']?.toString() ?? '',
      apellido: json['apellido']?.toString() ?? '',
      nombreUsuario: json['nombre_usuario']?.toString() ?? '',
      email: json['email']?.toString() ?? json['correo']?.toString(),
      telefono: json['telefono']?.toString(),
      rol: json['rol']?.toString() ?? 'cliente',
      puntosFidelidad: json['puntos_fidelidad'] is int
          ? json['puntos_fidelidad']
          : int.tryParse(json['puntos_fidelidad']?.toString() ?? '0') ?? 0,
      pedidosCount: json['pedidos_count'] is int
          ? json['pedidos_count']
          : int.tryParse(json['pedidos_count']?.toString() ?? '0') ?? 0,
      totalGastado:
          (json['total_gastado'] is num
              ? (json['total_gastado'] as num).toDouble()
              : double.tryParse(json['total_gastado']?.toString() ?? '0.0')) ??
          0.0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'nombre': nombre,
      'apellido': apellido,
      'nombre_usuario': nombreUsuario,
      'email': email,
      'telefono': telefono,
      'rol': rol,
      'puntos_fidelidad': puntosFidelidad,
      'pedidos_count': pedidosCount,
      'total_gastado': totalGastado,
    };
  }
}
