import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../providers/staff_provider.dart';
import '../../widgets/donde_david_card.dart';
import '../../widgets/status_badge.dart';

class DeliveryCourierScreen extends StatefulWidget {
  final StaffProvider? provider;

  const DeliveryCourierScreen({super.key, this.provider});

  @override
  State<DeliveryCourierScreen> createState() => _DeliveryCourierScreenState();
}

class _DeliveryCourierScreenState extends State<DeliveryCourierScreen> {
  @override
  void initState() {
    super.initState();
    widget.provider?.fetchCourierOrders();
  }

  void _openOtpDialog(int orderId, StaffProvider staff) {
    final otpCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: Text(
          'Entrega de Pedido #$orderId',
          style: const TextStyle(
            fontWeight: FontWeight.w900,
            color: Colors.white,
            fontSize: 16,
          ),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Solicita el código de entrega de 6 dígitos al cliente al entregarle el paquete:',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: otpCtrl,
              decoration: const InputDecoration(
                labelText: 'Código OTP (6 dígitos)',
                hintText: '123456',
              ),
              keyboardType: TextInputType.number,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () async {
              final ok = await staff.entregarDeliveryConOtp(
                orderId,
                otpCtrl.text.trim(),
              );
              if (mounted) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok
                          ? '¡Entrega confirmada y pedido completado! 🎉'
                          : staff.errorMessage ?? 'Código OTP incorrecto',
                    ),
                    backgroundColor: ok ? AppColors.success : AppColors.danger,
                  ),
                );
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.success),
            child: const Text('Validar y Entregar'),
          ),
        ],
      ),
    );
  }

  void _broadcastGpsLocation(
    int orderId,
    StaffProvider staff,
    double? lat,
    double? lng,
  ) async {
    // Coordenadas del cliente o Valencia Centro por defecto
    final targetLat = lat ?? 10.1800;
    final targetLng = lng ?? -67.9950;

    final ok = await staff.actualizarUbicacionRepartidor(
      orderId,
      targetLat,
      targetLng,
    );
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            ok
                ? '📡 Baliza GPS enviada en vivo al cliente (${targetLat.toStringAsFixed(4)}, ${targetLng.toStringAsFixed(4)})'
                : 'Error al compartir ubicación',
          ),
          backgroundColor: ok ? AppColors.electricTeal : AppColors.danger,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final staff = widget.provider;
    final orders = staff?.courierOrders ?? [];

    final asignadas = orders
        .where((o) => (o.estadoDelivery ?? 'ASIGNADO') == 'ASIGNADO')
        .length;
    final enRuta = orders
        .where(
          (o) =>
              (o.estadoDelivery ?? '') == 'EN_CAMINO' ||
              (o.estadoDelivery ?? '') == 'RECOGIDO',
        )
        .length;
    final porEntregar = orders
        .where((o) => (o.estadoDelivery ?? '') != 'ENTREGADO')
        .length;

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '🛵 PANEL DE REPARTIDOR',
          style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Actualizar entregas',
            onPressed: () => staff?.fetchCourierOrders(),
          ),
        ],
      ),
      body: staff == null
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: () => staff.fetchCourierOrders(),
              color: AppColors.goldAccent,
              child: ListView(
                padding: const EdgeInsets.all(14),
                children: [
                  // 1. Resumen de Entregas (Estilo Cashea del sistema web)
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          AppColors.electricTeal.withAlpha(25),
                          AppColors.goldAccent.withAlpha(20),
                        ],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: AppColors.electricTeal.withAlpha(140),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Icon(
                              Icons.two_wheeler,
                              color: AppColors.electricTeal,
                              size: 24,
                            ),
                            SizedBox(width: 8),
                            Text(
                              'PANEL DE RUTA Y DESPACHO',
                              style: TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w900,
                                fontSize: 14,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Tus entregas asignadas, navegación GPS y validación OTP en un solo lugar.',
                          style: TextStyle(
                            color: AppColors.textMuted,
                            fontSize: 11,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            _buildStatCard(
                              'Asignadas',
                              asignadas,
                              AppColors.warning,
                            ),
                            const SizedBox(width: 8),
                            _buildStatCard(
                              'En Ruta',
                              enRuta,
                              AppColors.electricTeal,
                            ),
                            const SizedBox(width: 8),
                            _buildStatCard(
                              'Por Entregar',
                              porEntregar,
                              AppColors.goldAccent,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 16),

                  const Text(
                    'MIS ENTREGAS ACTIVAS:',
                    style: TextStyle(
                      color: AppColors.goldAccent,
                      fontWeight: FontWeight.w900,
                      fontSize: 12,
                      letterSpacing: 0.6,
                    ),
                  ),
                  const SizedBox(height: 8),

                  if (orders.isEmpty)
                    Container(
                      padding: const EdgeInsets.all(32),
                      alignment: Alignment.center,
                      child: const Column(
                        children: [
                          Icon(
                            Icons.check_circle_outline,
                            color: AppColors.success,
                            size: 48,
                          ),
                          SizedBox(height: 10),
                          Text(
                            'No tienes pedidos de delivery asignados en este momento 🎉',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color: AppColors.textMuted,
                              fontSize: 13,
                            ),
                          ),
                        ],
                      ),
                    )
                  else
                    ...orders.map((order) {
                      final deliveryState = order.estadoDelivery ?? 'ASIGNADO';

                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: DondeDavidCard(
                          borderColor: AppColors.brandBlue,
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  Row(
                                    children: [
                                      Text(
                                        'PEDIDO #${order.id}',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.w900,
                                          fontSize: 16,
                                          color: AppColors.goldAccent,
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Text(
                                        '\$${order.total.toStringAsFixed(2)}',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.w800,
                                          fontSize: 13,
                                          color: Colors.white,
                                        ),
                                      ),
                                    ],
                                  ),
                                  StatusBadge(status: deliveryState),
                                ],
                              ),
                              const Divider(height: 14),

                              // Customer Info
                              Row(
                                children: [
                                  const Icon(
                                    Icons.person,
                                    size: 16,
                                    color: AppColors.cyanAccent,
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    order.deliveryNombre ?? 'Cliente Delivery',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w800,
                                      fontSize: 13,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Row(
                                children: [
                                  const Icon(
                                    Icons.phone,
                                    size: 16,
                                    color: AppColors.success,
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    order.deliveryTelefono ?? 'Sin teléfono',
                                    style: const TextStyle(
                                      fontSize: 12,
                                      color: AppColors.textSecondary,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  const Icon(
                                    Icons.location_on,
                                    size: 16,
                                    color: AppColors.danger,
                                  ),
                                  const SizedBox(width: 6),
                                  Expanded(
                                    child: Text(
                                      order.deliveryDireccion ??
                                          'Valencia, Carabobo',
                                      style: const TextStyle(
                                        fontSize: 12,
                                        color: AppColors.textPrimary,
                                      ),
                                    ),
                                  ),
                                ],
                              ),

                              const SizedBox(height: 10),

                              // Quick Contact & Navigation Shortcuts
                              Row(
                                children: [
                                  Expanded(
                                    child: OutlinedButton.icon(
                                      onPressed: () => _broadcastGpsLocation(
                                        order.id,
                                        staff,
                                        order.deliveryLat,
                                        order.deliveryLng,
                                      ),
                                      icon: const Icon(
                                        Icons.gps_fixed,
                                        size: 14,
                                      ),
                                      label: const Text(
                                        'Baliza GPS',
                                        style: TextStyle(fontSize: 10),
                                      ),
                                      style: OutlinedButton.styleFrom(
                                        foregroundColor: AppColors.electricTeal,
                                        side: const BorderSide(
                                          color: AppColors.electricTeal,
                                        ),
                                        padding: const EdgeInsets.symmetric(
                                          vertical: 4,
                                        ),
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: OutlinedButton.icon(
                                      onPressed: () {
                                        ScaffoldMessenger.of(
                                          context,
                                        ).showSnackBar(
                                          SnackBar(
                                            content: Text(
                                              'Llamando a ${order.deliveryTelefono ?? "cliente"}...',
                                            ),
                                          ),
                                        );
                                      },
                                      icon: const Icon(Icons.call, size: 14),
                                      label: const Text(
                                        'Llamar',
                                        style: TextStyle(fontSize: 10),
                                      ),
                                      style: OutlinedButton.styleFrom(
                                        foregroundColor: AppColors.success,
                                        side: const BorderSide(
                                          color: AppColors.success,
                                        ),
                                        padding: const EdgeInsets.symmetric(
                                          vertical: 4,
                                        ),
                                      ),
                                    ),
                                  ),
                                ],
                              ),

                              const Divider(height: 14),

                              // Delivery State Progress Action
                              if (deliveryState == 'ASIGNADO')
                                ElevatedButton.icon(
                                  onPressed: () =>
                                      staff.actualizarEstadoDelivery(
                                        order.id,
                                        'RECOGIDO',
                                      ),
                                  icon: const Icon(Icons.restaurant, size: 16),
                                  label: const Text(
                                    '📦 RECOGER EN RESTAURANTE',
                                  ),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppColors.brandOrange,
                                    minimumSize: const Size.fromHeight(42),
                                    foregroundColor: Colors.black,
                                  ),
                                )
                              else if (deliveryState == 'RECOGIDO')
                                ElevatedButton.icon(
                                  onPressed: () =>
                                      staff.actualizarEstadoDelivery(
                                        order.id,
                                        'EN_CAMINO',
                                      ),
                                  icon: const Icon(Icons.two_wheeler, size: 16),
                                  label: const Text(
                                    '🛵 INICIAR RUTA (EN CAMINO)',
                                  ),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppColors.brandBlue,
                                    minimumSize: const Size.fromHeight(42),
                                  ),
                                )
                              else if (deliveryState == 'EN_CAMINO')
                                ElevatedButton.icon(
                                  onPressed: () =>
                                      _openOtpDialog(order.id, staff),
                                  icon: const Icon(
                                    Icons.verified_user,
                                    size: 16,
                                  ),
                                  label: const Text(
                                    '🔐 CONFIRMAR ENTREGA CON OTP',
                                  ),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: AppColors.success,
                                    minimumSize: const Size.fromHeight(42),
                                    foregroundColor: Colors.black,
                                  ),
                                )
                              else
                                const Text(
                                  '✅ Pedido entregado exitosamente',
                                  style: TextStyle(
                                    color: AppColors.success,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                            ],
                          ),
                        ),
                      );
                    }),
                ],
              ),
            ),
    );
  }

  Widget _buildStatCard(String label, int val, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 8),
        decoration: BoxDecoration(
          color: AppColors.bgSurface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withAlpha(120)),
        ),
        child: Column(
          children: [
            Text(
              '$val',
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.w900,
                fontSize: 18,
              ),
            ),
            Text(
              label,
              style: const TextStyle(
                color: AppColors.textMuted,
                fontSize: 10,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
