import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../models/producto.dart';
import 'donde_david_button.dart';
import 'donde_david_dish_image.dart';

class ProductDetailSheet extends StatefulWidget {
  final Producto product;
  final double tasaCambioBs;
  final Function({
    required Producto product,
    required int quantity,
    required List<ProductoExtra> selectedExtras,
    required List<String> sinIngredientes,
    String? nota,
  })
  onAddToCart;

  const ProductDetailSheet({
    super.key,
    required this.product,
    required this.tasaCambioBs,
    required this.onAddToCart,
  });

  @override
  State<ProductDetailSheet> createState() => _ProductDetailSheetState();
}

class _ProductDetailSheetState extends State<ProductDetailSheet> {
  int _quantity = 1;
  final List<ProductoExtra> _selectedExtras = [];
  final List<String> _sinIngredientes = [];
  final TextEditingController _noteController = TextEditingController();

  final List<String> _commonIngredients = [
    'Cebolla',
    'Pepinillos',
    'Mostaza',
    'Mayonesa',
    'Tomate',
    'Lechuga',
  ];

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  double get _unitPrice {
    double total = widget.product.precio;
    for (var extra in _selectedExtras) {
      total += extra.precio;
    }
    return total;
  }

  double get _totalPrice => _unitPrice * _quantity;

  @override
  Widget build(BuildContext context) {
    final double totalBs = _totalPrice * widget.tasaCambioBs;

    return Container(
      decoration: const BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom + 16,
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Handle bar
            Center(
              child: Container(
                margin: const EdgeInsets.only(top: 10, bottom: 12),
                width: 40,
                height: 4,
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),

            // Hero Product Image
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
              child: DondeDavidDishImage(
                rawImageUrl: widget.product.imagenUrl,
                productName: widget.product.nombre,
                height: 170,
                width: double.infinity,
                borderRadius: BorderRadius.circular(16),
              ),
            ),

            // Product Header Info
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.product.nombre,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 18,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          widget.product.descripcion,
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 13,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        '\$${widget.product.precio.toStringAsFixed(2)}',
                        style: const TextStyle(
                          color: AppColors.goldAccent,
                          fontSize: 18,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      Text(
                        'Bs. ${(widget.product.precio * widget.tasaCambioBs).toStringAsFixed(2)}',
                        style: const TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            if (widget.product.alergenos != null &&
                widget.product.alergenos!.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 10, 20, 0),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.warning.withAlpha(25),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.warning.withAlpha(80)),
                  ),
                  child: Row(
                    children: [
                      const Icon(
                        Icons.warning_amber,
                        color: AppColors.warning,
                        size: 16,
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          'Alérgenos: ${widget.product.alergenos}',
                          style: const TextStyle(
                            color: AppColors.warning,
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            const Divider(height: 24),

            // Extras & Toppings Section
            if (widget.product.extras.isNotEmpty) ...[
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 20),
                child: Text(
                  '➕ AGREGAR EXTRAS / TOPPINGS',
                  style: TextStyle(
                    color: AppColors.cyanAccent,
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.5,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  children: widget.product.extras.map((extra) {
                    final isSelected = _selectedExtras.any(
                      (e) => e.nombre == extra.nombre,
                    );
                    return InkWell(
                      onTap: () {
                        setState(() {
                          if (isSelected) {
                            _selectedExtras.removeWhere(
                              (e) => e.nombre == extra.nombre,
                            );
                          } else {
                            _selectedExtras.add(extra);
                          }
                        });
                      },
                      borderRadius: BorderRadius.circular(10),
                      child: Container(
                        margin: const EdgeInsets.only(bottom: 6),
                        padding: const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 8,
                        ),
                        decoration: BoxDecoration(
                          color: isSelected
                              ? AppColors.cyanAccent.withAlpha(30)
                              : const Color(0xFF1E293B).withAlpha(100),
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: isSelected
                                ? AppColors.cyanAccent
                                : AppColors.border,
                          ),
                        ),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Row(
                              children: [
                                Icon(
                                  isSelected
                                      ? Icons.check_box
                                      : Icons.check_box_outline_blank,
                                  color: isSelected
                                      ? AppColors.cyanAccent
                                      : AppColors.textMuted,
                                  size: 18,
                                ),
                                const SizedBox(width: 8),
                                Text(
                                  extra.nombre,
                                  style: TextStyle(
                                    color: isSelected
                                        ? AppColors.textPrimary
                                        : AppColors.textSecondary,
                                    fontSize: 13,
                                    fontWeight: isSelected
                                        ? FontWeight.w800
                                        : FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                            Text(
                              '+ \$${extra.precio.toStringAsFixed(2)}',
                              style: const TextStyle(
                                color: AppColors.goldAccent,
                                fontSize: 12,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ),
              const SizedBox(height: 12),
            ],

            // Ingredients Exclusion (Sin cebolla, etc.)
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 20),
              child: Text(
                '🚫 ¿QUITAR ALGÚN INGREDIENTE?',
                style: TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 0.5,
                ),
              ),
            ),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Wrap(
                spacing: 6,
                runSpacing: 6,
                children: _commonIngredients.map((ing) {
                  final isExcluded = _sinIngredientes.contains(ing);
                  return FilterChip(
                    label: Text(
                      'Sin $ing',
                      style: TextStyle(
                        color: isExcluded
                            ? Colors.white
                            : AppColors.textSecondary,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    selected: isExcluded,
                    onSelected: (selected) {
                      setState(() {
                        if (selected) {
                          _sinIngredientes.add(ing);
                        } else {
                          _sinIngredientes.remove(ing);
                        }
                      });
                    },
                    selectedColor: AppColors.danger.withAlpha(200),
                    backgroundColor: const Color(0xFF1E293B).withAlpha(120),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                      side: BorderSide(
                        color: isExcluded ? AppColors.danger : AppColors.border,
                      ),
                    ),
                    showCheckmark: false,
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
                  );
                }).toList(),
              ),
            ),

            const SizedBox(height: 12),

            // Note input
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: TextField(
                controller: _noteController,
                maxLines: 2,
                decoration: const InputDecoration(
                  hintText:
                      'Instrucciones especiales para cocina (ej. bien tostado)...',
                  prefixIcon: Icon(Icons.edit_note, color: AppColors.textMuted),
                ),
                style: const TextStyle(fontSize: 13),
              ),
            ),

            const Divider(height: 24),

            // Bottom Actions: Quantity + Add Button
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  // Quantity Counter
                  Container(
                    decoration: BoxDecoration(
                      color: const Color(0xFF1E293B),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Row(
                      children: [
                        IconButton(
                          onPressed: () {
                            if (_quantity > 1) {
                              setState(() => _quantity--);
                            }
                          },
                          icon: const Icon(Icons.remove, size: 16),
                          visualDensity: VisualDensity.compact,
                        ),
                        Text(
                          '$_quantity',
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w900,
                            color: AppColors.textPrimary,
                          ),
                        ),
                        IconButton(
                          onPressed: () {
                            if (_quantity < 20) {
                              setState(() => _quantity++);
                            }
                          },
                          icon: const Icon(Icons.add, size: 16),
                          visualDensity: VisualDensity.compact,
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(width: 12),

                  // Add to Cart Button
                  Expanded(
                    child: DondeDavidButton(
                      text:
                          'AGREGAR · \$${_totalPrice.toStringAsFixed(2)} (Bs. ${totalBs.toStringAsFixed(1)})',
                      variant: ButtonVariant.gold,
                      onPressed: () {
                        widget.onAddToCart(
                          product: widget.product,
                          quantity: _quantity,
                          selectedExtras: _selectedExtras,
                          sinIngredientes: _sinIngredientes,
                          nota: _noteController.text.trim().isNotEmpty
                              ? _noteController.text.trim()
                              : null,
                        );
                        Navigator.pop(context);
                      },
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
