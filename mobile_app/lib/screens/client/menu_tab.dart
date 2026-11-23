import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/producto.dart';
import '../../providers/cart_provider.dart';
import '../../providers/catalog_provider.dart';
import '../../widgets/product_card.dart';
import '../../widgets/product_detail_sheet.dart';

class MenuTab extends StatefulWidget {
  final CatalogProvider catalog;
  final CartProvider cart;

  const MenuTab({super.key, required this.catalog, required this.cart});

  @override
  State<MenuTab> createState() => _MenuTabState();
}

class _MenuTabState extends State<MenuTab> {
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _searchController.text = widget.catalog.searchQuery;
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _openProductDetail(BuildContext context, Producto product) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => ProductDetailSheet(
        product: product,
        tasaCambioBs: widget.catalog.tasaCambioBs,
        onAddToCart:
            ({
              required product,
              required quantity,
              required selectedExtras,
              required sinIngredientes,
              nota,
            }) {
              widget.cart.addItem(
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
    final products = widget.catalog.filteredProducts;
    final tasaBs = widget.catalog.tasaCambioBs;

    return Column(
      children: [
        // Search & Category Filters Bar
        Container(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 10),
          decoration: const BoxDecoration(
            color: AppColors.bgSurface,
            border: Border(bottom: BorderSide(color: AppColors.border)),
          ),
          child: Column(
            children: [
              // Search Input
              TextField(
                controller: _searchController,
                onChanged: (val) => widget.catalog.setSearchQuery(val),
                decoration: InputDecoration(
                  hintText: '🔍 Buscar hamburguesa, ingrediente...',
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 10,
                  ),
                  suffixIcon: _searchController.text.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear, size: 16),
                          onPressed: () {
                            _searchController.clear();
                            widget.catalog.setSearchQuery('');
                          },
                        )
                      : null,
                ),
                style: const TextStyle(fontSize: 13),
              ),

              const SizedBox(height: 10),

              // Horizontal Category Chips
              SizedBox(
                height: 36,
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: widget.catalog.categories.length + 1,
                  separatorBuilder: (_, __) => const SizedBox(width: 8),
                  itemBuilder: (context, index) {
                    if (index == 0) {
                      final isSelected =
                          widget.catalog.selectedCategoryId == null;
                      return ChoiceChip(
                        label: const Text('Todo'),
                        selected: isSelected,
                        onSelected: (_) => widget.catalog.selectCategory(null),
                        selectedColor: AppColors.brandOrange,
                        backgroundColor: const Color(0xFF1E293B),
                        labelStyle: TextStyle(
                          color: isSelected
                              ? Colors.white
                              : AppColors.textSecondary,
                          fontWeight: FontWeight.w800,
                          fontSize: 11,
                        ),
                      );
                    }
                    final cat = widget.catalog.categories[index - 1];
                    final isSelected =
                        widget.catalog.selectedCategoryId == cat.id;
                    return ChoiceChip(
                      label: Text(cat.nombre),
                      selected: isSelected,
                      onSelected: (_) => widget.catalog.selectCategory(cat.id),
                      selectedColor: AppColors.brandOrange,
                      backgroundColor: const Color(0xFF1E293B),
                      labelStyle: TextStyle(
                        color: isSelected
                            ? Colors.white
                            : AppColors.textSecondary,
                        fontWeight: FontWeight.w800,
                        fontSize: 11,
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),

        // Products Grid
        Expanded(
          child: widget.catalog.isLoading
              ? const Center(
                  child: CircularProgressIndicator(color: AppColors.goldAccent),
                )
              : products.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(
                        Icons.search_off,
                        size: 48,
                        color: AppColors.textMuted,
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'No se encontraron productos coincidentes',
                        style: TextStyle(
                          color: AppColors.textSecondary,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 6),
                      TextButton(
                        onPressed: () {
                          _searchController.clear();
                          widget.catalog.setSearchQuery('');
                          widget.catalog.selectCategory(null);
                        },
                        child: const Text(
                          'Limpiar filtros',
                          style: TextStyle(color: AppColors.cyanAccent),
                        ),
                      ),
                    ],
                  ),
                )
              : GridView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 90),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    childAspectRatio: 0.72,
                    crossAxisSpacing: 10,
                    mainAxisSpacing: 10,
                  ),
                  itemCount: products.length,
                  itemBuilder: (context, index) {
                    final product = products[index];
                    return ProductCard(
                      product: product,
                      tasaCambioBs: tasaBs,
                      onAdd: () => _openProductDetail(context, product),
                      onTap: () => _openProductDetail(context, product),
                    );
                  },
                ),
        ),
      ],
    );
  }
}
