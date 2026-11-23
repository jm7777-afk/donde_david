class Categoria {
  final int id;
  final String nombre;
  final String? icono;
  final int orden;

  Categoria({
    required this.id,
    required this.nombre,
    this.icono,
    this.orden = 0,
  });

  factory Categoria.fromJson(Map<String, dynamic> json) {
    return Categoria(
      id: json['id'] is int
          ? json['id']
          : int.tryParse(json['id']?.toString() ?? '0') ?? 0,
      nombre: json['nombre']?.toString() ?? '',
      icono: json['icono']?.toString(),
      orden: json['orden'] is int
          ? json['orden']
          : int.tryParse(json['orden']?.toString() ?? '0') ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {'id': id, 'nombre': nombre, 'icono': icono, 'orden': orden};
  }
}
