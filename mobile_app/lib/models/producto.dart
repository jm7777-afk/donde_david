import 'dart:convert';

class ProductoExtra {
  final String nombre;
  final double precio;

  ProductoExtra({required this.nombre, required this.precio});

  factory ProductoExtra.fromJson(Map<String, dynamic> json) {
    return ProductoExtra(
      nombre: json['nombre']?.toString() ?? '',
      precio:
          (json['precio'] is num
              ? (json['precio'] as num).toDouble()
              : double.tryParse(json['precio']?.toString() ?? '0.0')) ??
          0.0,
    );
  }

  Map<String, dynamic> toJson() => {'nombre': nombre, 'precio': precio};
}

class Producto {
  final int id;
  final String nombre;
  final String descripcion;
  final double precio;
  final String? imagenUrl;
  final int categoriaId;
  final bool disponible;
  final int stock;
  final int tiempoPreparacion;
  final String? alergenos;
  final List<ProductoExtra> extras;

  Producto({
    required this.id,
    required this.nombre,
    required this.descripcion,
    required this.precio,
    this.imagenUrl,
    required this.categoriaId,
    this.disponible = true,
    this.stock = 10,
    this.tiempoPreparacion = 15,
    this.alergenos,
    this.extras = const [],
  });

  String? resolveImageUrl(String baseUrl) {
    if (imagenUrl == null || imagenUrl!.isEmpty) return null;
    if (imagenUrl!.startsWith('http://') || imagenUrl!.startsWith('https://')) {
      return imagenUrl;
    }
    final cleanBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    final cleanPath = imagenUrl!.startsWith('/') ? imagenUrl! : '/$imagenUrl';
    return '$cleanBase$cleanPath';
  }

  factory Producto.fromJson(Map<String, dynamic> json) {
    List<ProductoExtra> parsedExtras = [];
    final rawExtras = json['extras_json'];
    if (rawExtras != null) {
      try {
        dynamic decoded = rawExtras;
        if (rawExtras is String && rawExtras.isNotEmpty) {
          decoded = jsonDecode(rawExtras);
        }
        if (decoded is List) {
          parsedExtras = decoded
              .whereType<Map<String, dynamic>>()
              .map((e) => ProductoExtra.fromJson(e))
              .toList();
        }
      } catch (_) {}
    }

    return Producto(
      id: json['id'] is int
          ? json['id']
          : int.tryParse(json['id']?.toString() ?? '0') ?? 0,
      nombre: json['nombre']?.toString() ?? '',
      descripcion: json['descripcion']?.toString() ?? '',
      precio:
          (json['precio'] is num
              ? (json['precio'] as num).toDouble()
              : double.tryParse(json['precio']?.toString() ?? '0.0')) ??
          0.0,
      imagenUrl: json['imagen_url']?.toString(),
      categoriaId: json['categoria_id'] is int
          ? json['categoria_id']
          : int.tryParse(json['categoria_id']?.toString() ?? '0') ?? 0,
      disponible: json['disponible'] is bool
          ? json['disponible']
          : (json['disponible']?.toString().toLowerCase() == 'true'),
      stock: json['stock'] is int
          ? json['stock']
          : int.tryParse(json['stock']?.toString() ?? '0') ?? 0,
      tiempoPreparacion: json['tiempo_preparacion'] is int
          ? json['tiempo_preparacion']
          : int.tryParse(json['tiempo_preparacion']?.toString() ?? '15') ?? 15,
      alergenos: json['alergenos']?.toString(),
      extras: parsedExtras,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'nombre': nombre,
      'descripcion': descripcion,
      'precio': precio,
      'imagen_url': imagenUrl,
      'categoria_id': categoriaId,
      'disponible': disponible,
      'stock': stock,
      'tiempo_preparacion': tiempoPreparacion,
      'alergenos': alergenos,
      'extras_json': extras.map((e) => e.toJson()).toList(),
    };
  }
}
