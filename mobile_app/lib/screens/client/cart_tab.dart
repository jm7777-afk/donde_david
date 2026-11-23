import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../providers/cart_provider.dart';
import '../../providers/catalog_provider.dart';
import '../../providers/order_provider.dart';
import '../../widgets/delivery_map_modal.dart';
import '../../widgets/donde_david_button.dart';
import '../../widgets/donde_david_card.dart';
import '../../widgets/donde_david_dish_image.dart';
import '../../widgets/qr_scanner_dialog.dart';
import '../../widgets/status_badge.dart';

class CartTab extends StatefulWidget {
  final CartProvider cart;
  final CatalogProvider catalog;
  final OrderProvider order;
  final VoidCallback onGoToMenu;

  const CartTab({
    super.key,
    required this.cart,
    required this.catalog,
    required this.order,
    required this.onGoToMenu,
  });

  @override
  State<CartTab> createState() => _CartTabState();
}

class _CartTabState extends State<CartTab> {
  int _currentStep =
      1; // 1: Cart, 2: Entrega, 3: Resumen, 4: Pago, 5: Seguimiento

  // Controllers for delivery
  final TextEditingController _delivNombreCtrl = TextEditingController();
  final TextEditingController _delivTelCtrl = TextEditingController();
  final TextEditingController _delivDirCtrl = TextEditingController();
  final TextEditingController _payRefCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _delivNombreCtrl.text = widget.cart.deliveryNombre;
    _delivTelCtrl.text = widget.cart.deliveryTelefono;
    _delivDirCtrl.text = widget.cart.deliveryDireccion;
    _payRefCtrl.text = widget.cart.paymentReference;

    // If order was already submitted and currently tracked, show step 5
    if (widget.order.currentTrackedOrder != null && widget.cart.isEmpty) {
      _currentStep = 5;
    }
  }

  @override
  void dispose() {
    _delivNombreCtrl.dispose();
    _delivTelCtrl.dispose();
    _delivDirCtrl.dispose();
    _payRefCtrl.dispose();
    super.dispose();
  }

  void _openQrModal() {
    showDialog(
      context: context,
      builder: (_) => QrScannerDialog(
        currentTable: widget.catalog.activeTable,
        onTableSelected: (t) => widget.catalog.setActiveTable(t),
        onClearTable: () => widget.catalog.clearActiveTable(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget.cart.isEmpty && _currentStep < 5) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(
                Icons.shopping_cart_outlined,
                size: 72,
                color: AppColors.textMuted,
              ),
              const SizedBox(height: 16),
              const Text(
                'Tu carrito está vacío',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Explora nuestras hamburguesas, perros calientes y bebidas para armar tu pedido.',
                style: TextStyle(fontSize: 12, color: AppColors.textMuted),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              DondeDavidButton(
                text: '🚀 EXPLORAR EL MENÚ',
                variant: ButtonVariant.gold,
                onPressed: widget.onGoToMenu,
              ),
            ],
          ),
        ),
      );
    }

    return Column(
      children: [
        // 5-Step Progress Indicator
        _buildStepProgressIndicator(),

        // Step Content
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 90),
            child: _buildCurrentStepView(),
          ),
        ),
      ],
    );
  }

  // ================= 5-STEP INDICATOR =================
  Widget _buildStepProgressIndicator() {
    final steps = ['Carrito', 'Entrega', 'Resumen', 'Pago', 'Seguimiento'];

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: const BoxDecoration(
        color: AppColors.bgSurface,
        border: Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: List.generate(steps.length, (index) {
          final stepNum = index + 1;
          final isActive = _currentStep == stepNum;
          final isDone = _currentStep > stepNum;

          return Expanded(
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 26,
                        height: 26,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: isDone
                              ? AppColors.success
                              : isActive
                              ? AppColors.goldAccent
                              : const Color(0xFF1E293B),
                          border: Border.all(
                            color: isActive
                                ? AppColors.goldAccent
                                : AppColors.border,
                            width: 1.5,
                          ),
                        ),
                        child: Center(
                          child: isDone
                              ? const Icon(
                                  Icons.check,
                                  size: 14,
                                  color: Colors.black,
                                )
                              : Text(
                                  '$stepNum',
                                  style: TextStyle(
                                    color: isActive
                                        ? Colors.black
                                        : AppColors.textMuted,
                                    fontSize: 11,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        steps[index],
                        style: TextStyle(
                          color: isActive
                              ? AppColors.goldAccent
                              : isDone
                              ? AppColors.textPrimary
                              : AppColors.textMuted,
                          fontSize: 9,
                          fontWeight: isActive
                              ? FontWeight.w900
                              : FontWeight.w600,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
                if (index < steps.length - 1)
                  Container(
                    width: 12,
                    height: 2,
                    color: isDone ? AppColors.success : AppColors.border,
                    margin: const EdgeInsets.only(bottom: 14),
                  ),
              ],
            ),
          );
        }),
      ),
    );
  }

  Widget _buildCurrentStepView() {
    switch (_currentStep) {
      case 1:
        return _buildStep1Cart();
      case 2:
        return _buildStep2Delivery();
      case 3:
        return _buildStep3Summary();
      case 4:
        return _buildStep4Payment();
      case 5:
        return _buildStep5Tracking();
      default:
        return _buildStep1Cart();
    }
  }

  // ================= STEP 1: CART =================
  Widget _buildStep1Cart() {
    final tax = widget.cart.calculateTax(widget.catalog.impuestoPorcentaje);
    final deliv = widget.cart.calculateDeliveryFee(
      widget.catalog.costoDelivery,
    );
    final emp = widget.cart.calculateEmpaqueFee(widget.catalog.costoEmpaque);
    final total = widget.cart.calculateTotal(
      taxPercent: widget.catalog.impuestoPorcentaje,
      deliveryCost: widget.catalog.costoDelivery,
      empaqueCost: widget.catalog.costoEmpaque,
    );
    final totalBs = total * widget.catalog.tasaCambioBs;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'TU PEDIDO (${widget.cart.itemCount} ARTÍCULOS)',
              style: const TextStyle(
                color: AppColors.goldAccent,
                fontSize: 13,
                fontWeight: FontWeight.w900,
                letterSpacing: 0.5,
              ),
            ),
            TextButton(
              onPressed: () => widget.cart.clearCart(),
              child: const Text(
                'Vaciar',
                style: TextStyle(color: AppColors.danger, fontSize: 11),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),

        // List of Cart Items
        ListView.separated(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: widget.cart.items.length,
          separatorBuilder: (_, __) => const SizedBox(height: 8),
          itemBuilder: (context, index) {
            final item = widget.cart.items[index];
            return Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.bgCard,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppColors.border),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  DondeDavidDishImage(
                    rawImageUrl: item.product.imagenUrl,
                    productName: item.product.nombre,
                    width: 50,
                    height: 50,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.product.nombre,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontWeight: FontWeight.w800,
                            fontSize: 13,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '\$${item.unitPrice.toStringAsFixed(2)} c/u',
                          style: const TextStyle(
                            color: AppColors.goldAccent,
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        if (item.selectedExtras.isNotEmpty)
                          Text(
                            'Extras: ${item.selectedExtras.map((e) => e.nombre).join(", ")}',
                            style: const TextStyle(
                              color: AppColors.cyanAccent,
                              fontSize: 10,
                            ),
                          ),
                        if (item.sinIngredientes.isNotEmpty)
                          Text(
                            'Sin: ${item.sinIngredientes.join(", ")}',
                            style: const TextStyle(
                              color: AppColors.danger,
                              fontSize: 10,
                            ),
                          ),
                        if (item.nota != null && item.nota!.isNotEmpty)
                          Text(
                            'Nota: ${item.nota}',
                            style: const TextStyle(
                              color: AppColors.textMuted,
                              fontSize: 10,
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                      ],
                    ),
                  ),

                  // Quantity Controls
                  Row(
                    children: [
                      IconButton(
                        onPressed: () => widget.cart.decrementQuantity(index),
                        icon: const Icon(
                          Icons.remove_circle_outline,
                          color: AppColors.textMuted,
                          size: 20,
                        ),
                        visualDensity: VisualDensity.compact,
                      ),
                      Text(
                        '${item.quantity}',
                        style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontWeight: FontWeight.w900,
                          fontSize: 14,
                        ),
                      ),
                      IconButton(
                        onPressed: () => widget.cart.incrementQuantity(index),
                        icon: const Icon(
                          Icons.add_circle_outline,
                          color: AppColors.goldAccent,
                          size: 20,
                        ),
                        visualDensity: VisualDensity.compact,
                      ),
                    ],
                  ),
                ],
              ),
            );
          },
        ),

        const SizedBox(height: 16),

        // Cost Breakdown Card
        DondeDavidCard(
          padding: const EdgeInsets.all(14),
          child: Column(
            children: [
              _buildCostRow(
                'Subtotal productos',
                '\$${widget.cart.subtotal.toStringAsFixed(2)}',
              ),
              const SizedBox(height: 6),
              _buildCostRow(
                'IVA (${widget.catalog.impuestoPorcentaje.toInt()}%)',
                '\$${tax.toStringAsFixed(2)}',
              ),
              if (deliv > 0) ...[
                const SizedBox(height: 6),
                _buildCostRow(
                  'Costo de envío (Delivery)',
                  '\$${deliv.toStringAsFixed(2)}',
                ),
              ],
              if (emp > 0) ...[
                const SizedBox(height: 6),
                _buildCostRow(
                  'Empaque para llevar',
                  '\$${emp.toStringAsFixed(2)}',
                ),
              ],
              const Divider(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'TOTAL ESTIMADO',
                    style: TextStyle(
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.w900,
                      fontSize: 14,
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        '\$${total.toStringAsFixed(2)}',
                        style: const TextStyle(
                          color: AppColors.goldAccent,
                          fontWeight: FontWeight.w900,
                          fontSize: 18,
                        ),
                      ),
                      Text(
                        'Bs. ${totalBs.toStringAsFixed(2)}',
                        style: const TextStyle(
                          color: AppColors.textSecondary,
                          fontWeight: FontWeight.w700,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),

        const SizedBox(height: 20),

        DondeDavidButton(
          text: 'CONTINUAR · ENTREGA →',
          variant: ButtonVariant.gold,
          width: double.infinity,
          onPressed: () => setState(() => _currentStep = 2),
        ),
      ],
    );
  }

  // ================= STEP 2: DELIVERY =================
  Widget _buildStep2Delivery() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'PASO 2 DE 5: ¿CÓMO RECIBIRÁS TU PEDIDO?',
          style: TextStyle(
            color: AppColors.goldAccent,
            fontSize: 13,
            fontWeight: FontWeight.w900,
            letterSpacing: 0.5,
          ),
        ),
        const SizedBox(height: 12),

        // Order Type Selector
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14),
          decoration: BoxDecoration(
            color: AppColors.bgCard,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border),
          ),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<String>(
              value: widget.cart.orderType,
              isExpanded: true,
              dropdownColor: AppColors.bgSurface,
              items: const [
                DropdownMenuItem(
                  value: 'mesa',
                  child: Text('🍽️ Pedido en Local / Mesa (Vía QR)'),
                ),
                DropdownMenuItem(
                  value: 'delivery',
                  child: Text('🛵 Delivery (Entrega a Domicilio)'),
                ),
                DropdownMenuItem(
                  value: 'llevar',
                  child: Text('🛍️ Para Llevar / Mostrador'),
                ),
              ],
              onChanged: (val) {
                if (val != null) {
                  setState(() => widget.cart.setOrderType(val));
                }
              },
            ),
          ),
        ),

        const SizedBox(height: 16),

        // Conditional Details: MESA
        if (widget.cart.orderType == 'mesa') ...[
          DondeDavidCard(
            borderColor: AppColors.cyanAccent,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      '📱 UBICACIÓN EN MESA',
                      style: TextStyle(
                        color: AppColors.cyanAccent,
                        fontWeight: FontWeight.w900,
                        fontSize: 12,
                      ),
                    ),
                    TextButton.icon(
                      onPressed: _openQrModal,
                      icon: const Icon(
                        Icons.qr_code,
                        size: 14,
                        color: AppColors.cyanAccent,
                      ),
                      label: const Text(
                        'Escanear / Cambiar',
                        style: TextStyle(
                          color: AppColors.cyanAccent,
                          fontSize: 11,
                        ),
                      ),
                    ),
                  ],
                ),
                Text(
                  widget.catalog.activeTable != null
                      ? 'Estás pidiendo directamente en: ${widget.catalog.activeTable}'
                      : 'No has seleccionado una mesa aún. Pulsa escanear para vincular tu mesa.',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  'MODALIDAD DE COBRO EN MESA:',
                  style: TextStyle(
                    color: AppColors.textMuted,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                InkWell(
                  onTap: () =>
                      setState(() => widget.cart.setPaymentMode('PAGAR_ANTES')),
                  borderRadius: BorderRadius.circular(10),
                  child: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: widget.cart.paymentMode == 'PAGAR_ANTES'
                          ? AppColors.goldAccent.withAlpha(25)
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: widget.cart.paymentMode == 'PAGAR_ANTES'
                            ? AppColors.goldAccent
                            : AppColors.border,
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          widget.cart.paymentMode == 'PAGAR_ANTES'
                              ? Icons.radio_button_checked
                              : Icons.radio_button_off,
                          color: widget.cart.paymentMode == 'PAGAR_ANTES'
                              ? AppColors.goldAccent
                              : AppColors.textMuted,
                          size: 18,
                        ),
                        const SizedBox(width: 8),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Pagar antes (Caja / Pago Móvil)',
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                              Text(
                                'Pagas ahora y cocina prepara de inmediato.',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: AppColors.textMuted,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                InkWell(
                  onTap: () => setState(
                    () => widget.cart.setPaymentMode('PAGAR_DESPUES'),
                  ),
                  borderRadius: BorderRadius.circular(10),
                  child: Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: widget.cart.paymentMode == 'PAGAR_DESPUES'
                          ? AppColors.goldAccent.withAlpha(25)
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: widget.cart.paymentMode == 'PAGAR_DESPUES'
                            ? AppColors.goldAccent
                            : AppColors.border,
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          widget.cart.paymentMode == 'PAGAR_DESPUES'
                              ? Icons.radio_button_checked
                              : Icons.radio_button_off,
                          color: widget.cart.paymentMode == 'PAGAR_DESPUES'
                              ? AppColors.goldAccent
                              : AppColors.textMuted,
                          size: 18,
                        ),
                        const SizedBox(width: 8),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Cuenta abierta',
                                style: TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                              Text(
                                'Disfruta en mesa y cancela en Caja al salir.',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: AppColors.textMuted,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],

        // Conditional Details: DELIVERY
        if (widget.cart.orderType == 'delivery') ...[
          DondeDavidCard(
            borderColor: AppColors.brandBlue,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '🛵 DATOS DE ENTREGA A DOMICILIO',
                  style: TextStyle(
                    color: AppColors.brandBlue,
                    fontWeight: FontWeight.w900,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _delivNombreCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Nombre de quien recibe',
                  ),
                  style: const TextStyle(fontSize: 13),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _delivTelCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Teléfono WhatsApp de contacto',
                  ),
                  keyboardType: TextInputType.phone,
                  style: const TextStyle(fontSize: 13),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: _delivDirCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Dirección exacta / Punto de referencia',
                    hintText: 'Av., edificio, piso, o referencia visible',
                  ),
                  maxLines: 2,
                  style: const TextStyle(fontSize: 13),
                ),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: () {
                    showDialog(
                      context: context,
                      builder: (_) => DeliveryMapModal(
                        initialLat: widget.cart.deliveryLat,
                        initialLng: widget.cart.deliveryLng,
                        onLocationConfirmed: (lat, lng, ref) {
                          if (_delivDirCtrl.text.isEmpty) {
                            _delivDirCtrl.text = ref;
                          }
                          widget.cart.setDeliveryDetails(
                            nombre: _delivNombreCtrl.text,
                            telefono: _delivTelCtrl.text,
                            direccion: _delivDirCtrl.text,
                            lat: lat,
                            lng: lng,
                          );
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                '📍 Punto en el mapa fijado: (${lat.toStringAsFixed(4)}, ${lng.toStringAsFixed(4)})',
                              ),
                            ),
                          );
                        },
                      ),
                    );
                  },
                  icon: const Icon(
                    Icons.map,
                    size: 16,
                    color: AppColors.goldAccent,
                  ),
                  label: const Text(
                    '🗺️ Elegir punto en el mapa interactivo',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800),
                  ),
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: AppColors.goldAccent),
                    foregroundColor: AppColors.goldAccent,
                    minimumSize: const Size.fromHeight(40),
                  ),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: () {
                    // Quick simulated GPS
                    widget.cart.setDeliveryDetails(
                      nombre: _delivNombreCtrl.text,
                      telefono: _delivTelCtrl.text,
                      direccion: _delivDirCtrl.text,
                      lat: 10.1800,
                      lng: -68.0000,
                    );
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('📍 Ubicación GPS agregada al pedido.'),
                      ),
                    );
                  },
                  icon: const Icon(
                    Icons.my_location,
                    size: 16,
                    color: AppColors.cyanAccent,
                  ),
                  label: const Text(
                    'Adjuntar mi ubicación GPS actual',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800),
                  ),
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: AppColors.cyanAccent),
                    foregroundColor: AppColors.cyanAccent,
                    minimumSize: const Size.fromHeight(40),
                  ),
                ),
              ],
            ),
          ),
        ],

        // Conditional Details: LLEVAR
        if (widget.cart.orderType == 'llevar') ...[
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppColors.goldAccent.withAlpha(20),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.goldAccent.withAlpha(80)),
            ),
            child: const Row(
              children: [
                Icon(Icons.storefront, color: AppColors.goldAccent, size: 28),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Retirarás tu pedido en el mostrador del restaurante. Se generará un código de retiro de 6 dígitos que presentarás en Caja.',
                    style: TextStyle(color: Colors.white, fontSize: 12),
                  ),
                ),
              ],
            ),
          ),
        ],

        const SizedBox(height: 24),

        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => setState(() => _currentStep = 1),
                child: const Text('← Volver'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: DondeDavidButton(
                text: 'RESUMEN →',
                variant: ButtonVariant.gold,
                onPressed: () {
                  if (widget.cart.orderType == 'delivery') {
                    widget.cart.setDeliveryDetails(
                      nombre: _delivNombreCtrl.text,
                      telefono: _delivTelCtrl.text,
                      direccion: _delivDirCtrl.text,
                      lat: widget.cart.deliveryLat,
                      lng: widget.cart.deliveryLng,
                    );
                  }
                  setState(() => _currentStep = 3);
                },
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ================= STEP 3: SUMMARY =================
  Widget _buildStep3Summary() {
    final tax = widget.cart.calculateTax(widget.catalog.impuestoPorcentaje);
    final deliv = widget.cart.calculateDeliveryFee(
      widget.catalog.costoDelivery,
    );
    final emp = widget.cart.calculateEmpaqueFee(widget.catalog.costoEmpaque);
    final total = widget.cart.calculateTotal(
      taxPercent: widget.catalog.impuestoPorcentaje,
      deliveryCost: widget.catalog.costoDelivery,
      empaqueCost: widget.catalog.costoEmpaque,
    );
    final totalBs = total * widget.catalog.tasaCambioBs;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'PASO 3 DE 5: REVISA ANTES DE PAGAR',
          style: TextStyle(
            color: AppColors.goldAccent,
            fontSize: 13,
            fontWeight: FontWeight.w900,
            letterSpacing: 0.5,
          ),
        ),
        const SizedBox(height: 12),

        DondeDavidCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'DESTINO: ${widget.cart.orderType.toUpperCase()} ${widget.cart.orderType == "mesa" ? (widget.catalog.activeTable ?? "Mesa General") : ""}',
                style: const TextStyle(
                  color: AppColors.cyanAccent,
                  fontWeight: FontWeight.w900,
                  fontSize: 12,
                ),
              ),
              const Divider(height: 16),
              ...widget.cart.items.map(
                (i) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        '${i.quantity}x ${i.product.nombre}',
                        style: const TextStyle(fontSize: 12),
                      ),
                      Text(
                        '\$${i.subtotal.toStringAsFixed(2)}',
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
              _buildCostRow(
                'Subtotal',
                '\$${widget.cart.subtotal.toStringAsFixed(2)}',
              ),
              _buildCostRow('Impuesto', '\$${tax.toStringAsFixed(2)}'),
              if (deliv > 0)
                _buildCostRow('Delivery', '\$${deliv.toStringAsFixed(2)}'),
              if (emp > 0)
                _buildCostRow('Empaque', '\$${emp.toStringAsFixed(2)}'),
              const SizedBox(height: 6),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'Total a pagar',
                    style: TextStyle(fontWeight: FontWeight.w900, fontSize: 15),
                  ),
                  Text(
                    '\$${total.toStringAsFixed(2)} (Bs. ${totalBs.toStringAsFixed(2)})',
                    style: const TextStyle(
                      color: AppColors.goldAccent,
                      fontWeight: FontWeight.w900,
                      fontSize: 16,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                '🎁 Puntos estimados al pagar: ${widget.cart.estimatedPoints} pts',
                style: const TextStyle(
                  color: AppColors.cyanAccent,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 24),

        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => setState(() => _currentStep = 2),
                child: const Text('← Volver'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: DondeDavidButton(
                text: widget.cart.paymentMode == 'PAGAR_DESPUES'
                    ? 'CONFIRMAR PEDIDO →'
                    : 'PAGO →',
                variant: ButtonVariant.gold,
                onPressed: () {
                  if (widget.cart.paymentMode == 'PAGAR_DESPUES') {
                    _submitFinalOrder();
                  } else {
                    setState(() => _currentStep = 4);
                  }
                },
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ================= STEP 4: PAYMENT =================
  Widget _buildStep4Payment() {
    final total = widget.cart.calculateTotal(
      taxPercent: widget.catalog.impuestoPorcentaje,
      deliveryCost: widget.catalog.costoDelivery,
      empaqueCost: widget.catalog.costoEmpaque,
    );
    final totalBs = total * widget.catalog.tasaCambioBs;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'PASO 4 DE 5: SELECCIONA CÓMO PAGAR',
          style: TextStyle(
            color: AppColors.goldAccent,
            fontSize: 13,
            fontWeight: FontWeight.w900,
            letterSpacing: 0.5,
          ),
        ),
        const SizedBox(height: 12),

        DondeDavidCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'FORMA DE PAGO:',
                style: TextStyle(
                  color: AppColors.textMuted,
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              DropdownButtonFormField<String>(
                initialValue: widget.cart.paymentMethod,
                decoration: const InputDecoration(
                  contentPadding: EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                ),
                dropdownColor: AppColors.bgSurface,
                items: const [
                  DropdownMenuItem(
                    value: 'Efectivo',
                    child: Text('💵 Efectivo (USD o Bs.)'),
                  ),
                  DropdownMenuItem(
                    value: 'Punto de Venta',
                    child: Text('💳 Punto de venta en Caja'),
                  ),
                  DropdownMenuItem(
                    value: 'Pago Móvil',
                    child: Text('📱 Pago Móvil (verificación manual)'),
                  ),
                ],
                onChanged: (val) {
                  if (val != null)
                    setState(() => widget.cart.setPaymentMethod(val));
                },
              ),

              const SizedBox(height: 14),

              const Text(
                'MONEDA DE PAGO:',
                style: TextStyle(
                  color: AppColors.textMuted,
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 6),
              DropdownButtonFormField<String>(
                initialValue: widget.cart.paymentCurrency,
                decoration: const InputDecoration(
                  contentPadding: EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                ),
                dropdownColor: AppColors.bgSurface,
                items: [
                  DropdownMenuItem(
                    value: 'VES',
                    child: Text('Bolívares: Bs. ${totalBs.toStringAsFixed(2)}'),
                  ),
                  DropdownMenuItem(
                    value: 'USD',
                    child: Text('Dólares: \$${total.toStringAsFixed(2)} USD'),
                  ),
                ],
                onChanged: (val) {
                  if (val != null)
                    setState(() => widget.cart.setPaymentCurrency(val));
                },
              ),

              if (widget.cart.paymentMethod == 'Pago Móvil') ...[
                const SizedBox(height: 14),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.cyanAccent.withAlpha(20),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: AppColors.cyanAccent.withAlpha(100),
                    ),
                  ),
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'DATOS BANCARIOS PAGO MÓVIL:',
                        style: TextStyle(
                          color: AppColors.cyanAccent,
                          fontWeight: FontWeight.w800,
                          fontSize: 11,
                        ),
                      ),
                      SizedBox(height: 4),
                      Text(
                        'Banco: 0102 - Banco de Venezuela\nTeléfono: 0414-1234567\nRif: J-12345678-0',
                        style: TextStyle(color: Colors.white, fontSize: 12),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _payRefCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Número de referencia bancaria',
                    hintText: 'Ej. 823491',
                  ),
                  keyboardType: TextInputType.number,
                  style: const TextStyle(fontSize: 13),
                  onChanged: (v) => widget.cart.setPaymentReference(v),
                ),
              ],
            ],
          ),
        ),

        const SizedBox(height: 24),

        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: () => setState(() => _currentStep = 3),
                child: const Text('← Volver'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: DondeDavidButton(
                text: 'ENVIAR PEDIDO 🚀',
                variant: ButtonVariant.gold,
                isLoading: widget.order.isSubmitting,
                onPressed: _submitFinalOrder,
              ),
            ),
          ],
        ),
      ],
    );
  }

  // ================= STEP 5: TRACKING =================
  Widget _buildStep5Tracking() {
    final order = widget.order.currentTrackedOrder;

    if (order == null) {
      return Center(
        child: Column(
          children: [
            const Text('No hay ningún pedido activo en seguimiento.'),
            const SizedBox(height: 12),
            DondeDavidButton(
              text: 'Volver al Menú',
              onPressed: widget.onGoToMenu,
            ),
          ],
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        DondeDavidCard(
          padding: const EdgeInsets.all(20),
          borderColor: AppColors.goldAccent,
          child: Column(
            children: [
              const Text('🔥', style: TextStyle(fontSize: 40)),
              const SizedBox(height: 6),
              Text(
                'PEDIDO #${order.id}',
                style: const TextStyle(
                  color: AppColors.goldAccent,
                  fontWeight: FontWeight.w900,
                  fontSize: 20,
                  letterSpacing: 1,
                ),
              ),
              const SizedBox(height: 10),
              StatusBadge(status: order.estado),
              const SizedBox(height: 12),
              Text(
                'Modalidad: ${order.tipo.toUpperCase()} • Total: \$${order.total.toStringAsFixed(2)}',
                style: const TextStyle(
                  color: AppColors.textSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),

              // OTP code if delivery
              if (order.otpEntrega != null && order.otpEntrega!.isNotEmpty) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.cyanAccent.withAlpha(20),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.cyanAccent),
                  ),
                  child: Column(
                    children: [
                      const Text(
                        '🔐 CÓDIGO DE ENTREGA OTP:',
                        style: TextStyle(
                          color: AppColors.cyanAccent,
                          fontSize: 11,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        order.otpEntrega!,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 24,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 3,
                        ),
                      ),
                      const Text(
                        'Entrégaselo al repartidor al recibir tu pedido.',
                        style: TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 10,
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              // Takeaway Pickup Code
              if (order.codigoRetiro != null &&
                  order.codigoRetiro!.isNotEmpty) ...[
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.goldAccent.withAlpha(20),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.goldAccent),
                  ),
                  child: Column(
                    children: [
                      const Text(
                        '🛍️ CÓDIGO DE RETIRO EN CAJA:',
                        style: TextStyle(
                          color: AppColors.goldAccent,
                          fontSize: 11,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        order.codigoRetiro!,
                        style: const TextStyle(
                          color: AppColors.goldAccent,
                          fontSize: 26,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 4,
                        ),
                      ),
                      const Text(
                        'Muéstralo en Caja para retirar tu comida.',
                        style: TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 10,
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              const Divider(height: 24),

              OutlinedButton.icon(
                onPressed: () => widget.order.refreshTrackedOrder(order.id),
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Actualizar estado'),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(40),
                ),
              ),
              const SizedBox(height: 10),
              DondeDavidButton(
                text: '⭐ CALIFICAR EL SERVICIO',
                variant: ButtonVariant.gold,
                width: double.infinity,
                onPressed: () => _openServiceRatingDialog(order.id),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _submitFinalOrder() async {
    final tableNumber = widget.catalog.activeTable ?? 'Mesa 1';
    final createdOrder = await widget.order.submitOrder(
      cart: widget.cart,
      tableNumber: tableNumber,
    );

    if (createdOrder != null && mounted) {
      setState(() => _currentStep = 5);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('¡Pedido #${createdOrder.id} creado con éxito!'),
        ),
      );
    } else if (mounted && widget.order.errorMessage != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(widget.order.errorMessage!),
          backgroundColor: AppColors.danger,
        ),
      );
    }
  }

  void _openServiceRatingDialog(int orderId) {
    int rating = 5;
    final commentCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (_) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text(
            'Calificar Servicio',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(5, (index) {
                  final star = index + 1;
                  return IconButton(
                    icon: Icon(
                      star <= rating ? Icons.star : Icons.star_border,
                      color: AppColors.goldAccent,
                      size: 28,
                    ),
                    onPressed: () => setDialogState(() => rating = star),
                  );
                }),
              ),
              TextField(
                controller: commentCtrl,
                decoration: const InputDecoration(
                  hintText: 'Escribe tu opinión...',
                ),
                maxLines: 2,
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () async {
                await widget.order.submitServiceReview(
                  clientName: 'Cliente Mesa',
                  rating: rating,
                  comment: commentCtrl.text.trim().isNotEmpty
                      ? commentCtrl.text.trim()
                      : 'Excelente comida y atención.',
                );
                if (mounted) {
                  Navigator.pop(ctx);
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('¡Gracias por tu calificación! ⭐'),
                    ),
                  );
                }
              },
              child: const Text('Enviar'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCostRow(String title, String amount) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          title,
          style: const TextStyle(color: AppColors.textMuted, fontSize: 12),
        ),
        Text(
          amount,
          style: const TextStyle(
            color: AppColors.textSecondary,
            fontSize: 12,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}
