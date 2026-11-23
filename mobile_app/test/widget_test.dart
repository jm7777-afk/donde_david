import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/models/producto.dart';
import 'package:mobile_app/models/usuario.dart';
import 'package:mobile_app/models/mesa.dart';
import 'package:mobile_app/providers/cart_provider.dart';

void main() {
  group('Model Tests', () {
    test('Producto model deserialization test', () {
      final json = {
        'id': 1,
        'nombre': 'Burger Clásica',
        'descripcion': 'Carne 100% res',
        'precio': 7.50,
        'categoria_id': 1,
        'disponible': true,
        'stock': 12,
        'tiempo_preparacion': 10,
        'extras_json': [
          {'nombre': 'Tocineta', 'precio': 1.50},
          {'nombre': 'Queso Cheddar', 'precio': 1.00},
        ],
      };

      final prod = Producto.fromJson(json);
      expect(prod.id, 1);
      expect(prod.nombre, 'Burger Clásica');
      expect(prod.precio, 7.50);
      expect(prod.extras.length, 2);
      expect(prod.extras[0].nombre, 'Tocineta');
      expect(prod.extras[0].precio, 1.50);
    });

    test('Usuario model deserialization and staff check', () {
      final staffJson = {
        'id': 10,
        'nombre': 'David',
        'apellido': 'Cajero',
        'nombre_usuario': 'caja',
        'rol': 'caja',
        'puntos_fidelidad': 0,
      };

      final staff = Usuario.fromJson(staffJson);
      expect(staff.isStaff, true);
      expect(staff.isCashier, true);
      expect(staff.isClient, false);

      final clientJson = {
        'id': 20,
        'nombre': 'Carlos',
        'apellido': 'Pérez',
        'nombre_usuario': 'carlos',
        'rol': 'cliente',
        'puntos_fidelidad': 50,
      };

      final client = Usuario.fromJson(clientJson);
      expect(client.isStaff, false);
      expect(client.isClient, true);
      expect(client.puntosFidelidad, 50);
    });

    test('Mesa model state test', () {
      final mesaJson = {
        'id': 5,
        'numero_mesa': 5,
        'estado': 'OCUPADA',
        'capacidad': 4,
        'tiempo_ocupacion_min': 25,
        'pedidos_activos': 1,
        'solicitudes_pendientes': 1,
      };

      final mesa = Mesa.fromJson(mesaJson);
      expect(mesa.numeroMesa, 5);
      expect(mesa.isOccupied, true);
      expect(mesa.isFree, false);
      expect(mesa.tiempoOcupacionMin, 25);
    });
  });

  group('Cart Calculation Tests', () {
    test('Cart calculations with tax, delivery and empaque', () {
      final cart = CartProvider();
      final prod1 = Producto(
        id: 1,
        nombre: 'Hamburguesa Doble',
        descripcion: 'Deliciosa',
        precio: 10.00,
        categoriaId: 1,
      );
      final prod2 = Producto(
        id: 2,
        nombre: 'Papas Fritas',
        descripcion: 'Crocantes',
        precio: 3.00,
        categoriaId: 2,
      );

      cart.addItem(product: prod1, quantity: 2); // $20.00
      cart.addItem(product: prod2, quantity: 1); // $3.00

      expect(cart.itemCount, 3);
      expect(cart.subtotal, 23.00);

      // Mesa mode (no delivery fee, no empaque fee)
      cart.setOrderType('mesa');
      double totalMesa = cart.calculateTotal(
        taxPercent: 16.0,
        deliveryCost: 5.0,
        empaqueCost: 1.0,
      );
      // 23.00 + (23 * 0.16 = 3.68) = 26.68
      expect(totalMesa, closeTo(26.68, 0.01));

      // Delivery mode (adds $5.00 delivery fee)
      cart.setOrderType('delivery');
      double totalDelivery = cart.calculateTotal(
        taxPercent: 16.0,
        deliveryCost: 5.0,
        empaqueCost: 1.0,
      );
      // 26.68 + 5.00 = 31.68
      expect(totalDelivery, closeTo(31.68, 0.01));

      // Llevar mode (adds $1.00 empaque fee)
      cart.setOrderType('llevar');
      double totalLlevar = cart.calculateTotal(
        taxPercent: 16.0,
        deliveryCost: 5.0,
        empaqueCost: 1.0,
      );
      // 26.68 + 1.00 = 27.68
      expect(totalLlevar, closeTo(27.68, 0.01));
    });
  });
}
