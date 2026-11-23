import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/producto.dart';
import '../../providers/auth_provider.dart';
import '../../providers/cart_provider.dart';
import '../../providers/catalog_provider.dart';
import '../../providers/order_provider.dart';
import '../../widgets/donde_david_card.dart';
import '../../widgets/product_card.dart';
import '../../widgets/product_detail_sheet.dart';

class HomeTab extends StatelessWidget {
  final CatalogProvider catalog;
  final CartProvider cart;
  final AuthProvider auth;
  final OrderProvider order;
  final VoidCallback onGoToMenu;
  final VoidCallback onOpenQrModal;
  final VoidCallback onOpenLoginModal;

  const HomeTab({
    super.key,
    required this.catalog,
    required this.cart,
    required this.auth,
    required this.order,
    required this.onGoToMenu,
    required this.onOpenQrModal,
    required this.onOpenLoginModal,
  });

  void _openProductDetail(BuildContext context, Producto product) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ProductDetailSheet(
        product: product,
        tasaCambioBs: catalog.tasaCambioBs,
        onAddToCart:
            ({
              required product,
              required quantity,
              required selectedExtras,
              required sinIngredientes,
              nota,
            }) {
              cart.addItem(
                product: product,
                quantity: quantity,
                selectedExtras: selectedExtras,
                sinIngredientes: sinIngredientes,
                nota: nota,
              );
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('¡${product.nombre} agregado al pedido!'),
                  duration: const Duration(seconds: 2),
                ),
              );
            },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final tasaBs = catalog.tasaCambioBs;

    return RefreshIndicator(
      onRefresh: () async {
        await catalog.loadCatalog();
        await order.fetchOrderHistory();
      },
      color: AppColors.goldAccent,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 90),
        children: [
          // Offline Indicator Banner if using local cache
          if (catalog.isOffline)
            Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: const Color(0xFF8A4B00),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.white.withAlpha(50)),
              ),
              child: const Row(
                children: [
                  Icon(Icons.wifi_off, color: Colors.white, size: 16),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Modo sin conexión: explorando el menú guardado en caché local.',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // 1. Welcome & Points Banner
          DondeDavidCard(
            padding: const EdgeInsets.all(14),
            borderColor: AppColors.goldAccent.withAlpha(120),
            gradient: const LinearGradient(
              colors: [Color(0x33FFC400), Color(0x150879E8)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    gradient: AppColors.goldGradient,
                    borderRadius: BorderRadius.circular(22),
                  ),
                  child: const Center(
                    child: Text('🎁', style: TextStyle(fontSize: 22)),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        auth.isAuthenticated
                            ? 'HOLA, ${auth.user?.nombre.toUpperCase() ?? "CLIENTE"}!'
                            : '¡BIENVENIDO A DONDE DAVID!',
                        style: const TextStyle(
                          color: AppColors.goldAccent,
                          fontWeight: FontWeight.w900,
                          fontSize: 12,
                          letterSpacing: 0.5,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        auth.isAuthenticated
                            ? 'Tienes ${auth.user?.puntosFidelidad ?? 0} Puntos de Fidelidad 🏆'
                            : 'Pide como invitado o ingresa para acumular puntos.',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ),
                if (!auth.isAuthenticated)
                  TextButton(
                    onPressed: onOpenLoginModal,
                    style: TextButton.styleFrom(
                      foregroundColor: AppColors.cyanAccent,
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                    ),
                    child: const Text(
                      'Entrar',
                      style: TextStyle(
                        fontWeight: FontWeight.w900,
                        fontSize: 12,
                      ),
                    ),
                  ),
              ],
            ),
          ),

          const SizedBox(height: 12),

          // 2. Table Service Actions (if table is active)
          if (catalog.activeTable != null) ...[
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.cyanAccent.withAlpha(20),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppColors.cyanAccent.withAlpha(100)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'ATENCIÓN EN ${catalog.activeTable!.toUpperCase()}',
                        style: const TextStyle(
                          color: AppColors.cyanAccent,
                          fontWeight: FontWeight.w900,
                          fontSize: 11,
                          letterSpacing: 0.5,
                        ),
                      ),
                      const Icon(
                        Icons.table_restaurant,
                        color: AppColors.cyanAccent,
                        size: 16,
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () async {
                            final ok = await order.sendTableServiceRequest(
                              tableNumber: catalog.activeTable!,
                              tipo: 'LLAMAR_MESERO',
                            );
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    ok
                                        ? '🙋 Mesero notificado a tu mesa.'
                                        : order.errorMessage ??
                                              'Error al llamar al mesero',
                                  ),
                                ),
                              );
                            }
                          },
                          icon: const Icon(
                            Icons.room_service,
                            size: 14,
                            color: AppColors.goldAccent,
                          ),
                          label: const Text(
                            'Llamar Mesero',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: AppColors.goldAccent),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 8),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () async {
                            final ok = await order.sendTableServiceRequest(
                              tableNumber: catalog.activeTable!,
                              tipo: 'SOLICITAR_CUENTA',
                            );
                            if (context.mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    ok
                                        ? '🧾 Solicitud de cuenta enviada a Caja.'
                                        : order.errorMessage ??
                                              'Error al solicitar cuenta',
                                  ),
                                ),
                              );
                            }
                          },
                          icon: const Icon(
                            Icons.receipt,
                            size: 14,
                            color: AppColors.cyanAccent,
                          ),
                          label: const Text(
                            'Pedir Cuenta',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: AppColors.cyanAccent),
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 8),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
          ],

          // 3. Official BCV Rate Card
          DondeDavidCard(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'TASA OFICIAL DEL DÍA BCV',
                      style: TextStyle(
                        color: AppColors.textMuted,
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Bs. ${tasaBs.toStringAsFixed(2)} / USD',
                      style: const TextStyle(
                        color: AppColors.goldAccent,
                        fontSize: 15,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                ),
                const Icon(
                  Icons.trending_up,
                  color: AppColors.goldAccent,
                  size: 28,
                ),
              ],
            ),
          ),

          const SizedBox(height: 12),

          // 4. Trust Badges
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _buildTrustBadge('🥩 Carne 100% Res'),
                const SizedBox(width: 8),
                _buildTrustBadge('⚡ Preparación <12 min'),
                const SizedBox(width: 8),
                _buildTrustBadge('📱 Pedido Directo Cocina'),
                const SizedBox(width: 8),
                _buildTrustBadge('🛵 Delivery Rápido'),
              ],
            ),
          ),

          const SizedBox(height: 16),

          // 5. Horizontal Categories Scroll
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                '🍔 CATEGORÍAS DEL MENÚ',
                style: TextStyle(
                  color: AppColors.goldAccent,
                  fontWeight: FontWeight.w900,
                  fontSize: 13,
                  letterSpacing: 0.6,
                ),
              ),
              InkWell(
                onTap: onGoToMenu,
                child: const Text(
                  'Ver menú completo →',
                  style: TextStyle(
                    color: AppColors.cyanAccent,
                    fontWeight: FontWeight.w800,
                    fontSize: 11,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),

          SizedBox(
            height: 38,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: catalog.categories.length + 1,
              separatorBuilder: (_, __) => const SizedBox(width: 8),
              itemBuilder: (context, index) {
                if (index == 0) {
                  final isSelected = catalog.selectedCategoryId == null;
                  return ChoiceChip(
                    label: const Text('Todos'),
                    selected: isSelected,
                    onSelected: (_) => catalog.selectCategory(null),
                    selectedColor: AppColors.brandOrange,
                    backgroundColor: const Color(0xFF1E293B),
                    labelStyle: TextStyle(
                      color: isSelected
                          ? Colors.white
                          : AppColors.textSecondary,
                      fontWeight: FontWeight.w800,
                      fontSize: 12,
                    ),
                  );
                }
                final cat = catalog.categories[index - 1];
                final isSelected = catalog.selectedCategoryId == cat.id;
                return ChoiceChip(
                  label: Text(cat.nombre),
                  selected: isSelected,
                  onSelected: (_) => catalog.selectCategory(cat.id),
                  selectedColor: AppColors.brandOrange,
                  backgroundColor: const Color(0xFF1E293B),
                  labelStyle: TextStyle(
                    color: isSelected ? Colors.white : AppColors.textSecondary,
                    fontWeight: FontWeight.w800,
                    fontSize: 12,
                  ),
                );
              },
            ),
          ),

          const SizedBox(height: 18),

          // 6. Featured Products Section
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                '🔥 LO MÁS PEDIDO Y DELICIOSO',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                  fontSize: 14,
                  letterSpacing: 0.5,
                ),
              ),
              Text(
                '${catalog.featuredProducts.length} platos',
                style: const TextStyle(
                  color: AppColors.textMuted,
                  fontSize: 11,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          if (catalog.isLoading)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(40),
                child: CircularProgressIndicator(color: AppColors.goldAccent),
              ),
            )
          else if (catalog.featuredProducts.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(30),
                child: Text(
                  'No hay productos disponibles en este momento.',
                  style: TextStyle(color: AppColors.textMuted),
                ),
              ),
            )
          else
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                childAspectRatio: 0.72,
                crossAxisSpacing: 10,
                mainAxisSpacing: 10,
              ),
              itemCount: catalog.featuredProducts.length,
              itemBuilder: (context, index) {
                final product = catalog.featuredProducts[index];
                return ProductCard(
                  product: product,
                  tasaCambioBs: tasaBs,
                  onAdd: () => _openProductDetail(context, product),
                  onTap: () => _openProductDetail(context, product),
                );
              },
            ),
        ],
      ),
    );
  }

  Widget _buildTrustBadge(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: Colors.white.withAlpha(10),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Colors.white,
          fontSize: 10,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
