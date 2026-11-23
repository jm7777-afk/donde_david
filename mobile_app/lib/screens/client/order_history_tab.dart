import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/pedido.dart';
import '../../providers/cart_provider.dart';
import '../../providers/catalog_provider.dart';
import '../../providers/order_provider.dart';
import '../../widgets/donde_david_card.dart';
import '../../widgets/status_badge.dart';

class OrderHistoryTab extends StatelessWidget {
  final OrderProvider order;
  final CatalogProvider catalog;
  final CartProvider cart;
  final Function(Pedido order) onTrackOrder;
  final VoidCallback onGoToMenu;

  const OrderHistoryTab({
    super.key,
    required this.order,
    required this.catalog,
    required this.cart,
    required this.onTrackOrder,
    required this.onGoToMenu,
  });

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () => order.fetchOrderHistory(),
      color: AppColors.goldAccent,
      child: order.isLoadingHistory
          ? const Center(
              child: CircularProgressIndicator(color: AppColors.goldAccent),
            )
          : order.orderHistory.isEmpty
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(
                      Icons.receipt_long,
                      size: 64,
                      color: AppColors.textMuted,
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      'Aún no tienes pedidos registrados',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Tus órdenes realizadas en mesa o delivery se guardarán aquí automáticamente.',
                      style: TextStyle(
                        color: AppColors.textMuted,
                        fontSize: 12,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton(
                      onPressed: onGoToMenu,
                      child: const Text('Comenzar un pedido'),
                    ),
                  ],
                ),
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 90),
              itemCount: order.orderHistory.length,
              separatorBuilder: (_, __) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final p = order.orderHistory[index];
                final dateStr = p.fechaCreacion != null
                    ? '${p.fechaCreacion!.day}/${p.fechaCreacion!.month}/${p.fechaCreacion!.year} ${p.fechaCreacion!.hour.toString().padLeft(2, "0")}:${p.fechaCreacion!.minute.toString().padLeft(2, "0")}'
                    : 'Fecha reciente';

                return DondeDavidCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              Text(
                                'PEDIDO #${p.id}',
                                style: const TextStyle(
                                  color: AppColors.goldAccent,
                                  fontWeight: FontWeight.w900,
                                  fontSize: 14,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Text(
                                '(${p.tipo.toUpperCase()})',
                                style: const TextStyle(
                                  color: AppColors.textMuted,
                                  fontSize: 11,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),
                          StatusBadge(status: p.estado),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Text(
                        dateStr,
                        style: const TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 11,
                        ),
                      ),
                      const Divider(height: 16),

                      // Items
                      ...p.detalles.map(
                        (d) => Padding(
                          padding: const EdgeInsets.symmetric(vertical: 2),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(
                                '${d.cantidad}x ${d.productoNombre}',
                                style: const TextStyle(fontSize: 12),
                              ),
                              Text(
                                '\$${d.subtotal.toStringAsFixed(2)}',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),

                      const Divider(height: 16),

                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Total: \$${p.total.toStringAsFixed(2)}',
                                style: const TextStyle(
                                  color: AppColors.textPrimary,
                                  fontWeight: FontWeight.w900,
                                  fontSize: 14,
                                ),
                              ),
                              Text(
                                'Bs. ${(p.total * catalog.tasaCambioBs).toStringAsFixed(2)}',
                                style: const TextStyle(
                                  color: AppColors.textMuted,
                                  fontSize: 10,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),

                          Row(
                            children: [
                              // Repeat Order Button
                              OutlinedButton.icon(
                                onPressed: () {
                                  // Re-add available products
                                  for (var item in p.detalles) {
                                    final product = catalog.products.firstWhere(
                                      (prod) => prod.id == item.productoId,
                                      orElse: () => catalog.products.first,
                                    );
                                    cart.addItem(
                                      product: product,
                                      quantity: item.cantidad,
                                    );
                                  }
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text(
                                        '⚡ ¡Productos del pedido anterior re-agregados al carrito!',
                                      ),
                                    ),
                                  );
                                },
                                icon: const Icon(
                                  Icons.replay,
                                  size: 14,
                                  color: AppColors.cyanAccent,
                                ),
                                label: const Text(
                                  'Repetir',
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                style: OutlinedButton.styleFrom(
                                  side: const BorderSide(
                                    color: AppColors.cyanAccent,
                                  ),
                                  foregroundColor: AppColors.cyanAccent,
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 10,
                                    vertical: 6,
                                  ),
                                  visualDensity: VisualDensity.compact,
                                ),
                              ),
                              const SizedBox(width: 6),

                              // Track Button
                              IconButton(
                                onPressed: () => onTrackOrder(p),
                                icon: const Icon(
                                  Icons.arrow_forward_ios,
                                  size: 14,
                                  color: AppColors.textSecondary,
                                ),
                                visualDensity: VisualDensity.compact,
                                tooltip: 'Ver seguimiento',
                              ),
                            ],
                          ),
                        ],
                      ),
                    ],
                  ),
                );
              },
            ),
    );
  }
}
