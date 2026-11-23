import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/producto.dart';
import '../../providers/catalog_provider.dart';
import '../../providers/staff_provider.dart';
import '../../widgets/donde_david_card.dart';
import '../../widgets/donde_david_dish_image.dart';
import '../../widgets/status_badge.dart';

class PosCashierScreen extends StatefulWidget {
  final StaffProvider? provider;
  final CatalogProvider? catalogProvider;

  const PosCashierScreen({super.key, this.provider, this.catalogProvider});

  @override
  State<PosCashierScreen> createState() => _PosCashierScreenState();
}

class _PosCashierScreenState extends State<PosCashierScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  // POS Touch State
  int? _selectedCategoryId;
  String _productSearch = '';
  final List<Map<String, dynamic>> _ticketItems = [];
  String _posModality = 'llevar'; // mesa, llevar, delivery
  String _posPaymentMethod = 'Efectivo'; // Efectivo, Pago Móvil, Punto de Venta
  String _posPaymentCurrency = 'USD'; // USD, VES
  final TextEditingController _tableOrCustomerCtrl = TextEditingController(
    text: 'Mostrador',
  );
  final TextEditingController _nitCtrl = TextEditingController(text: 'CF');
  final TextEditingController _cashReceivedCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
    widget.provider?.fetchCashierData();
    widget.provider?.fetchMovimientosCaja();
  }

  @override
  void dispose() {
    _tabController.dispose();
    _tableOrCustomerCtrl.dispose();
    _nitCtrl.dispose();
    _cashReceivedCtrl.dispose();
    super.dispose();
  }

  double get _ticketSubtotal {
    double sum = 0.0;
    for (var item in _ticketItems) {
      final Producto prod = item['producto'];
      final int qty = item['cantidad'];
      sum += prod.precio * qty;
    }
    return sum;
  }

  double get _ticketTax => _ticketSubtotal * 0.16;
  double get _ticketTotal => _ticketSubtotal + _ticketTax;

  void _addToTicket(Producto prod) {
    final idx = _ticketItems.indexWhere(
      (i) => (i['producto'] as Producto).id == prod.id,
    );
    if (idx >= 0) {
      setState(() {
        _ticketItems[idx]['cantidad'] =
            (_ticketItems[idx]['cantidad'] as int) + 1;
      });
    } else {
      setState(() {
        _ticketItems.add({'producto': prod, 'cantidad': 1});
      });
    }
  }

  void _removeFromTicket(int index) {
    setState(() {
      if ((_ticketItems[index]['cantidad'] as int) > 1) {
        _ticketItems[index]['cantidad'] =
            (_ticketItems[index]['cantidad'] as int) - 1;
      } else {
        _ticketItems.removeAt(index);
      }
    });
  }

  void _clearTicket() {
    setState(() {
      _ticketItems.clear();
      _cashReceivedCtrl.clear();
    });
  }

  void _openAbrirTurnoDialog(StaffProvider staff) {
    final ctrl = TextEditingController(text: '50.0');
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: const Text(
          '🔓 Abrir Turno de Caja',
          style: TextStyle(
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
              'Ingresa el monto de fondo inicial en caja en USD:',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: ctrl,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Fondo Apertura USD',
                prefixText: '\$ ',
              ),
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
              final val = double.tryParse(ctrl.text.trim()) ?? 0.0;
              final ok = await staff.abrirTurnoCaja(val);
              if (mounted) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok
                          ? '¡Turno abierto exitosamente!'
                          : staff.errorMessage ?? 'Error al abrir',
                    ),
                  ),
                );
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.success),
            child: const Text('Confirmar Apertura'),
          ),
        ],
      ),
    );
  }

  void _openCerrarTurnoDialog(StaffProvider staff) {
    final efCtrl = TextEditingController(text: '0.0');
    final pmCtrl = TextEditingController(text: '0.0');
    final posCtrl = TextEditingController(text: '0.0');

    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: const Text(
          '🔒 Cierre y Arqueo de Turno',
          style: TextStyle(
            fontWeight: FontWeight.w900,
            color: Colors.white,
            fontSize: 16,
          ),
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Ingresa los montos arqueados contados por cada medio de pago:',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: efCtrl,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Efectivo Contado (USD)',
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: pmCtrl,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Pago Móvil Equivalente (USD)',
                ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: posCtrl,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Punto de Venta / Tarjetas (USD)',
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () async {
              final ok = await staff.cerrarTurnoCaja(
                efectivo: double.tryParse(efCtrl.text) ?? 0.0,
                pagoMovil: double.tryParse(pmCtrl.text) ?? 0.0,
                puntoDeVenta: double.tryParse(posCtrl.text) ?? 0.0,
              );
              if (mounted) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok
                          ? '¡Turno cerrado y arqueo guardado!'
                          : staff.errorMessage ?? 'Error al cerrar turno',
                    ),
                  ),
                );
              }
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.danger),
            child: const Text('Confirmar Cierre'),
          ),
        ],
      ),
    );
  }

  void _openNuevoMovimientoDialog(StaffProvider staff) {
    final conceptoCtrl = TextEditingController();
    final montoCtrl = TextEditingController();
    String metodo = 'Efectivo';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDlgState) => AlertDialog(
          backgroundColor: AppColors.bgSurface,
          title: const Text(
            '💵 Movimiento de Caja',
            style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: conceptoCtrl,
                decoration: const InputDecoration(
                  labelText: 'Concepto',
                  hintText: 'Ej. Compra hielo, pago propina',
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: montoCtrl,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Monto USD',
                  prefixText: '\$ ',
                ),
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: metodo,
                items: const [
                  DropdownMenuItem(value: 'Efectivo', child: Text('Efectivo')),
                  DropdownMenuItem(
                    value: 'Pago Móvil',
                    child: Text('Pago Móvil'),
                  ),
                  DropdownMenuItem(
                    value: 'Punto de Venta',
                    child: Text('Punto de Venta'),
                  ),
                ],
                onChanged: (val) {
                  if (val != null) setDlgState(() => metodo = val);
                },
                decoration: const InputDecoration(labelText: 'Medio de Pago'),
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
                final monto = double.tryParse(montoCtrl.text) ?? 0.0;
                if (conceptoCtrl.text.trim().isEmpty || monto <= 0) return;
                final ok = await staff.registrarMovimientoCaja(
                  concepto: conceptoCtrl.text.trim(),
                  montoUsd: monto,
                  metodoPago: metodo,
                );
                if (mounted) {
                  Navigator.pop(ctx);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        ok
                            ? '¡Movimiento registrado con éxito!'
                            : staff.errorMessage ?? 'Error',
                      ),
                    ),
                  );
                }
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.brandOrange,
              ),
              child: const Text('Guardar'),
            ),
          ],
        ),
      ),
    );
  }

  void _openConfirmarRetiroDialog(int orderId, StaffProvider staff) {
    final codeCtrl = TextEditingController();
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: Text(
          'Entrega Pedido #$orderId',
          style: const TextStyle(fontWeight: FontWeight.w900),
        ),
        content: TextField(
          controller: codeCtrl,
          decoration: const InputDecoration(
            labelText: 'Código de Retiro (6 dígitos)',
            hintText: '123456',
          ),
          keyboardType: TextInputType.number,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () async {
              final ok = await staff.confirmarRetiroLlevar(
                orderId,
                codeCtrl.text.trim(),
              );
              if (mounted) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok
                          ? '¡Retiro confirmado exitosamente!'
                          : staff.errorMessage ?? 'Código inválido',
                    ),
                  ),
                );
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.goldAccent,
              foregroundColor: Colors.black,
            ),
            child: const Text('Confirmar'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final staff = widget.provider;
    final shift = staff?.turnoActivo;
    final isOpen = shift != null && shift.isOpen;
    final pendingCount = staff?.pendingCashierOrders.length ?? 0;
    final pickupCount = staff?.takeawayPickupOrders.length ?? 0;

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '💰 TERMINAL POS & CAJA',
          style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
        ),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: AppColors.goldAccent,
          labelColor: AppColors.goldAccent,
          unselectedLabelColor: AppColors.textMuted,
          isScrollable: true,
          tabs: [
            const Tab(icon: Icon(Icons.touch_app, size: 18), text: 'POS Touch'),
            Tab(
              icon: const Icon(Icons.receipt_long, size: 18),
              text: 'Por Cobrar ($pendingCount)',
            ),
            Tab(
              icon: const Icon(Icons.takeout_dining, size: 18),
              text: 'Retiros ($pickupCount)',
            ),
            const Tab(
              icon: Icon(Icons.account_balance_wallet, size: 18),
              text: 'Turno & Caja',
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Actualizar',
            onPressed: () {
              staff?.fetchCashierData();
              staff?.fetchMovimientosCaja();
            },
          ),
        ],
      ),
      body: staff == null
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildPosTouchTab(staff),
                _buildPendingOrdersList(staff),
                _buildTakeawayPickupList(staff),
                _buildShiftAndMovementsTab(staff, isOpen, shift),
              ],
            ),
    );
  }

  // ----------------------------------------------------
  // TAB 1: POS TOUCH (PUNTO DE VENTA RÁPIDO)
  // ----------------------------------------------------
  Widget _buildPosTouchTab(StaffProvider staff) {
    final catalog = widget.catalogProvider;
    final products = catalog?.products ?? [];
    final categories = catalog?.categories ?? [];
    final double tasaBs = catalog?.tasaCambioBs ?? 40.0;

    final filteredProducts = products.where((p) {
      if (!p.disponible) return false;
      if (_selectedCategoryId != null && p.categoriaId != _selectedCategoryId)
        return false;
      if (_productSearch.isNotEmpty) {
        return p.nombre.toLowerCase().contains(_productSearch.toLowerCase());
      }
      return true;
    }).toList();

    return Column(
      children: [
        // 1. Selector de Modalidad y Búsqueda
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          color: AppColors.bgSurface,
          child: Column(
            children: [
              Row(
                children: [
                  _buildModalityPill('llevar', '📦 Para Llevar'),
                  const SizedBox(width: 6),
                  _buildModalityPill('mesa', '🍽️ Mesa'),
                  const SizedBox(width: 6),
                  _buildModalityPill('delivery', '🛵 Delivery'),
                ],
              ),
              const SizedBox(height: 8),
              TextField(
                onChanged: (val) => setState(() => _productSearch = val),
                decoration: InputDecoration(
                  hintText: '🔍 Buscar producto en menú...',
                  isDense: true,
                  filled: true,
                  fillColor: AppColors.bgMain,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide.none,
                  ),
                  prefixIcon: const Icon(
                    Icons.search,
                    size: 20,
                    color: AppColors.goldAccent,
                  ),
                ),
              ),
            ],
          ),
        ),

        // 2. Filtro Horizontal de Categorías
        Container(
          height: 44,
          padding: const EdgeInsets.symmetric(vertical: 4),
          color: AppColors.navyDark,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 10),
            children: [
              _buildCategoryChip(null, '🔥 TODOS'),
              ...categories.map((c) => _buildCategoryChip(c.id, c.nombre)),
            ],
          ),
        ),

        // 3. Catálogo Grid de Productos
        Expanded(
          child: filteredProducts.isEmpty
              ? const Center(child: Text('No hay productos disponibles'))
              : GridView.builder(
                  padding: const EdgeInsets.all(10),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    childAspectRatio: 0.88,
                    crossAxisSpacing: 8,
                    mainAxisSpacing: 8,
                  ),
                  itemCount: filteredProducts.length,
                  itemBuilder: (context, idx) {
                    final prod = filteredProducts[idx];
                    final double priceBs = prod.precio * tasaBs;
                    return InkWell(
                      onTap: () => _addToTicket(prod),
                      borderRadius: BorderRadius.circular(12),
                      child: Container(
                        decoration: BoxDecoration(
                          color: AppColors.bgCard,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppColors.border),
                        ),
                        clipBehavior: Clip.antiAlias,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            DondeDavidDishImage(
                              rawImageUrl: prod.imagenUrl,
                              productName: prod.nombre,
                              height: 72,
                              width: double.infinity,
                            ),
                            Expanded(
                              child: Padding(
                                padding: const EdgeInsets.all(8),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      prod.nombre,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w900,
                                        fontSize: 12,
                                        color: Colors.white,
                                      ),
                                    ),
                                    Row(
                                      mainAxisAlignment:
                                          MainAxisAlignment.spaceBetween,
                                      children: [
                                        Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                            Text(
                                              '\$${prod.precio.toStringAsFixed(2)}',
                                              style: const TextStyle(
                                                color: AppColors.goldAccent,
                                                fontWeight: FontWeight.w900,
                                                fontSize: 13,
                                              ),
                                            ),
                                            Text(
                                              'Bs. ${priceBs.toStringAsFixed(1)}',
                                              style: const TextStyle(
                                                color: AppColors.textMuted,
                                                fontSize: 10,
                                              ),
                                            ),
                                          ],
                                        ),
                                        Container(
                                          padding: const EdgeInsets.all(5),
                                          decoration: const BoxDecoration(
                                            shape: BoxShape.circle,
                                            color: AppColors.brandOrange,
                                          ),
                                          child: const Icon(
                                            Icons.add,
                                            size: 14,
                                            color: Colors.black,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
        ),

        // 4. Ticket Resumen Flotante / Inferior
        _buildBottomTicketBar(staff, tasaBs),
      ],
    );
  }

  Widget _buildModalityPill(String key, String label) {
    final isSelected = _posModality == key;
    return Expanded(
      child: InkWell(
        onTap: () => setState(() {
          _posModality = key;
          _tableOrCustomerCtrl.text = key == 'mesa'
              ? 'Mesa 1'
              : (key == 'delivery' ? 'Delivery' : 'Mostrador');
        }),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 6),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.brandOrange : AppColors.bgMain,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isSelected ? AppColors.brandOrange : AppColors.border,
            ),
          ),
          child: Center(
            child: Text(
              label,
              style: TextStyle(
                color: isSelected ? Colors.black : Colors.white,
                fontWeight: FontWeight.w800,
                fontSize: 10,
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCategoryChip(int? catId, String title) {
    final isSelected = _selectedCategoryId == catId;
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: FilterChip(
        label: Text(
          title,
          style: TextStyle(
            color: isSelected ? Colors.black : Colors.white,
            fontSize: 10,
            fontWeight: FontWeight.w800,
          ),
        ),
        selected: isSelected,
        selectedColor: AppColors.goldAccent,
        backgroundColor: AppColors.bgSurface,
        onSelected: (_) => setState(() => _selectedCategoryId = catId),
      ),
    );
  }

  Widget _buildBottomTicketBar(StaffProvider staff, double tasaBs) {
    final totalUsd = _ticketTotal;
    final totalBs = totalUsd * tasaBs;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        border: const Border(
          top: BorderSide(color: AppColors.border, width: 1.5),
        ),
        boxShadow: const [
          BoxShadow(
            color: Colors.black54,
            blurRadius: 10,
            offset: Offset(0, -3),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  const Icon(
                    Icons.shopping_cart,
                    color: AppColors.goldAccent,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    '${_ticketItems.length} ítems en ticket',
                    style: const TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
              if (_ticketItems.isNotEmpty)
                InkWell(
                  onTap: _clearTicket,
                  child: const Text(
                    'Limpiar',
                    style: TextStyle(
                      color: AppColors.danger,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'TOTAL: \$${totalUsd.toStringAsFixed(2)} USD',
                      style: const TextStyle(
                        fontWeight: FontWeight.w900,
                        color: AppColors.goldAccent,
                        fontSize: 16,
                      ),
                    ),
                    Text(
                      'Equiv: Bs. ${totalBs.toStringAsFixed(2)}',
                      style: const TextStyle(
                        color: AppColors.electricTeal,
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              ElevatedButton.icon(
                onPressed: _ticketItems.isEmpty
                    ? null
                    : () => _showTicketCheckoutSheet(staff, tasaBs),
                icon: const Icon(Icons.bolt, size: 18),
                label: const Text('COBRAR POS'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.brandOrange,
                  foregroundColor: Colors.black,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _showTicketCheckoutSheet(StaffProvider staff, double tasaBs) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.bgSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (context, setSheetState) {
          final totalUsd = _ticketTotal;
          final totalBs = totalUsd * tasaBs;
          final receivedVal =
              double.tryParse(_cashReceivedCtrl.text) ?? totalUsd;
          final changeVal = receivedVal > totalUsd
              ? (receivedVal - totalUsd)
              : 0.0;

          return Padding(
            padding: EdgeInsets.only(
              left: 16,
              right: 16,
              top: 16,
              bottom: MediaQuery.of(context).viewInsets.bottom + 16,
            ),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        '🧾 FACTURACIÓN RÁPIDA POS',
                        style: TextStyle(
                          fontWeight: FontWeight.w900,
                          fontSize: 15,
                          color: Colors.white,
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () => Navigator.pop(ctx),
                      ),
                    ],
                  ),
                  const Divider(color: AppColors.border),

                  // Modality & Table Field
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _tableOrCustomerCtrl,
                          decoration: InputDecoration(
                            labelText: _posModality == 'mesa'
                                ? 'Número de Mesa'
                                : 'Identificador / Cliente',
                            isDense: true,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: _nitCtrl,
                          decoration: const InputDecoration(
                            labelText: 'RIF / C.I. Cliente',
                            isDense: true,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),

                  // Ítems List
                  Container(
                    constraints: const BoxConstraints(maxHeight: 140),
                    decoration: BoxDecoration(
                      color: AppColors.bgMain,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: ListView.separated(
                      shrinkWrap: true,
                      itemCount: _ticketItems.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (_, idx) {
                        final Producto prod = _ticketItems[idx]['producto'];
                        final int qty = _ticketItems[idx]['cantidad'];
                        return ListTile(
                          dense: true,
                          title: Text(
                            prod.nombre,
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              fontSize: 12,
                            ),
                          ),
                          subtitle: Text(
                            '\$${prod.precio.toStringAsFixed(2)} x $qty = \$${(prod.precio * qty).toStringAsFixed(2)}',
                          ),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                icon: const Icon(Icons.remove, size: 16),
                                onPressed: () =>
                                    setSheetState(() => _removeFromTicket(idx)),
                              ),
                              IconButton(
                                icon: const Icon(Icons.add, size: 16),
                                onPressed: () =>
                                    setSheetState(() => _addToTicket(prod)),
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                  ),

                  const SizedBox(height: 12),

                  // Métodos de Pago
                  const Text(
                    'Medio de Pago:',
                    style: TextStyle(
                      fontWeight: FontWeight.w800,
                      fontSize: 12,
                      color: AppColors.goldAccent,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Row(
                    children: [
                      _buildPayMethodButton(
                        'Efectivo',
                        Icons.money,
                        setSheetState,
                      ),
                      const SizedBox(width: 6),
                      _buildPayMethodButton(
                        'Pago Móvil',
                        Icons.phone_android,
                        setSheetState,
                      ),
                      const SizedBox(width: 6),
                      _buildPayMethodButton(
                        'Punto de Venta',
                        Icons.credit_card,
                        setSheetState,
                      ),
                    ],
                  ),

                  const SizedBox(height: 10),

                  // Monto recibido & Vuelto si es efectivo
                  if (_posPaymentMethod == 'Efectivo') ...[
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _cashReceivedCtrl,
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                            onChanged: (_) => setSheetState(() {}),
                            decoration: const InputDecoration(
                              labelText: 'Monto Recibido USD',
                              prefixText: '\$ ',
                              isDense: true,
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            const Text(
                              'Vuelto:',
                              style: TextStyle(
                                color: AppColors.textMuted,
                                fontSize: 10,
                              ),
                            ),
                            Text(
                              '\$${changeVal.toStringAsFixed(2)} USD',
                              style: const TextStyle(
                                color: AppColors.success,
                                fontWeight: FontWeight.w900,
                                fontSize: 14,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                  ],

                  // Totales y Botón de Cobro
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.navyLight,
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Total: \$${totalUsd.toStringAsFixed(2)} USD',
                              style: const TextStyle(
                                fontWeight: FontWeight.w900,
                                color: AppColors.goldAccent,
                                fontSize: 15,
                              ),
                            ),
                            Text(
                              'Bs. ${totalBs.toStringAsFixed(2)} (BCV)',
                              style: const TextStyle(
                                color: AppColors.electricTeal,
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                        ElevatedButton(
                          onPressed: () async {
                            final detalles = _ticketItems.map((i) {
                              final Producto p = i['producto'];
                              final int qty = i['cantidad'];
                              return {'producto_id': p.id, 'cantidad': qty};
                            }).toList();

                            final ok = await staff.crearYCobrarRapidoPos(
                              numeroMesa:
                                  _tableOrCustomerCtrl.text.trim().isEmpty
                                  ? 'Mostrador'
                                  : _tableOrCustomerCtrl.text.trim(),
                              tipo: _posModality,
                              metodoPago: _posPaymentMethod,
                              monedaPago: _posPaymentCurrency,
                              montoRecibido: receivedVal,
                              nitCliente: _nitCtrl.text.trim(),
                              nombreFactura: _tableOrCustomerCtrl.text.trim(),
                              detalles: detalles,
                            );

                            if (mounted) {
                              Navigator.pop(ctx);
                              if (ok) {
                                _clearTicket();
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text(
                                      '¡Venta cobrada y facturada con éxito! ✅',
                                    ),
                                    backgroundColor: AppColors.success,
                                  ),
                                );
                              } else {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text(
                                      staff.errorMessage ??
                                          'Error al procesar cobro',
                                    ),
                                    backgroundColor: AppColors.danger,
                                  ),
                                );
                              }
                            }
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.brandOrange,
                            foregroundColor: Colors.black,
                          ),
                          child: const Text(
                            'EMITIR FACTURA',
                            style: TextStyle(fontWeight: FontWeight.w900),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildPayMethodButton(
    String method,
    IconData icon,
    StateSetter setSheetState,
  ) {
    final isSelected = _posPaymentMethod == method;
    return Expanded(
      child: InkWell(
        onTap: () => setSheetState(() => _posPaymentMethod = method),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.goldAccent : AppColors.bgMain,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isSelected ? AppColors.goldAccent : AppColors.border,
            ),
          ),
          child: Column(
            children: [
              Icon(
                icon,
                size: 16,
                color: isSelected ? Colors.black : Colors.white,
              ),
              const SizedBox(height: 2),
              Text(
                method,
                style: TextStyle(
                  color: isSelected ? Colors.black : Colors.white,
                  fontWeight: FontWeight.w800,
                  fontSize: 9,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ----------------------------------------------------
  // TAB 2: PEDIDOS POR COBRAR & CUENTAS ABIERTAS
  // ----------------------------------------------------
  Widget _buildPendingOrdersList(StaffProvider staff) {
    final orders = staff.pendingCashierOrders;
    if (orders.isEmpty) {
      return const Center(
        child: Text(
          'No hay pedidos pendientes de cobro 🎉',
          style: TextStyle(color: AppColors.textMuted),
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(14),
      itemCount: orders.length,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        final order = orders[index];
        final isPagoMovilPending = order.estadoPago == 'PENDIENTE_VALIDACION';

        return DondeDavidCard(
          borderColor: isPagoMovilPending
              ? AppColors.warning
              : AppColors.border,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'PEDIDO #${order.id} · ${order.numeroMesa}',
                    style: const TextStyle(
                      fontWeight: FontWeight.w900,
                      fontSize: 14,
                    ),
                  ),
                  StatusBadge(status: order.estadoPago),
                ],
              ),
              const Divider(height: 14),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Tipo: ${order.tipo.toUpperCase()}',
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                    ),
                  ),
                  Text(
                    '\$${order.total.toStringAsFixed(2)} USD',
                    style: const TextStyle(
                      fontWeight: FontWeight.w900,
                      fontSize: 15,
                      color: AppColors.goldAccent,
                    ),
                  ),
                ],
              ),
              if (order.metodoPago != null) ...[
                const SizedBox(height: 4),
                Text(
                  'Método: ${order.metodoPago} (${order.monedaPago ?? "USD"})',
                  style: const TextStyle(
                    color: AppColors.electricTeal,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
              const SizedBox(height: 10),

              if (isPagoMovilPending) ...[
                Container(
                  padding: const EdgeInsets.all(8),
                  margin: const EdgeInsets.only(bottom: 8),
                  decoration: BoxDecoration(
                    color: AppColors.navyLight,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text(
                    '⚠️ Pago Móvil pendiente de conciliación bancaria.',
                    style: TextStyle(color: AppColors.warning, fontSize: 11),
                  ),
                ),
                Row(
                  children: [
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () => staff.validarPagoMovilCaja(order.id),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.success,
                        ),
                        child: const Text(
                          'Aprobar Pago',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => staff.rechazarPagoMovilCaja(
                          order.id,
                          'Referencia no encontrada',
                        ),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppColors.danger,
                          side: const BorderSide(color: AppColors.danger),
                        ),
                        child: const Text(
                          'Rechazar',
                          style: TextStyle(fontSize: 11),
                        ),
                      ),
                    ),
                  ],
                ),
              ] else ...[
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () => staff.cobrarPedidoCaja(
                      pedidoId: order.id,
                      metodoPago: 'Efectivo',
                      moneda: 'USD',
                      montoPagado: order.total,
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.brandOrange,
                      foregroundColor: Colors.black,
                    ),
                    child: const Text(
                      '⚡ COBRAR Y FACTURAR',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        );
      },
    );
  }

  // ----------------------------------------------------
  // TAB 3: RETIROS EN MOSTRADOR (LLEVAR)
  // ----------------------------------------------------
  Widget _buildTakeawayPickupList(StaffProvider staff) {
    final orders = staff.takeawayPickupOrders;
    if (orders.isEmpty) {
      return const Center(
        child: Text(
          'No hay pedidos listos para retiro en mostrador.',
          style: TextStyle(color: AppColors.textMuted),
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(14),
      itemCount: orders.length,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        final order = orders[index];
        return DondeDavidCard(
          borderColor: AppColors.goldAccent,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'PEDIDO #${order.id}',
                    style: const TextStyle(
                      fontWeight: FontWeight.w900,
                      color: AppColors.goldAccent,
                      fontSize: 15,
                    ),
                  ),
                  const Text(
                    'Para Llevar · Listo en Cocina',
                    style: TextStyle(color: AppColors.textMuted, fontSize: 11),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: () => _openConfirmarRetiroDialog(order.id, staff),
                icon: const Icon(Icons.check, size: 16),
                label: const Text('Validar PIN'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.goldAccent,
                  foregroundColor: Colors.black,
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  // ----------------------------------------------------
  // TAB 4: TURNO DE CAJA & MOVIMIENTOS
  // ----------------------------------------------------
  Widget _buildShiftAndMovementsTab(
    StaffProvider staff,
    bool isOpen,
    dynamic shift,
  ) {
    final movimientos = staff.movimientosCaja;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Shift Card
          DondeDavidCard(
            borderColor: isOpen ? AppColors.success : AppColors.danger,
            child: Column(
              children: [
                Icon(
                  isOpen ? Icons.lock_open : Icons.lock,
                  size: 44,
                  color: isOpen ? AppColors.success : AppColors.danger,
                ),
                const SizedBox(height: 8),
                Text(
                  isOpen
                      ? 'TURNO DE CAJA ACTIVO (# ${shift?.numeroTurno ?? 1})'
                      : 'NO HAY TURNO ABIERTO',
                  style: TextStyle(
                    fontWeight: FontWeight.w900,
                    fontSize: 15,
                    color: isOpen ? AppColors.success : AppColors.danger,
                  ),
                ),
                if (isOpen && shift != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    'Fondo Inicial: \$${shift.montoAperturaUsd.toStringAsFixed(2)} USD',
                    style: const TextStyle(
                      fontSize: 12,
                      color: AppColors.textMuted,
                    ),
                  ),
                  Text(
                    'Total Ventas Registradas: \$${shift.efectivoEsperado.toStringAsFixed(2)} USD',
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w900,
                      color: AppColors.goldAccent,
                    ),
                  ),
                ],
                const SizedBox(height: 14),
                if (!isOpen)
                  ElevatedButton.icon(
                    onPressed: () => _openAbrirTurnoDialog(staff),
                    icon: const Icon(Icons.lock_open),
                    label: const Text('ABRIR TURNO DE CAJA'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.success,
                      minimumSize: const Size.fromHeight(44),
                    ),
                  )
                else
                  ElevatedButton.icon(
                    onPressed: () => _openCerrarTurnoDialog(staff),
                    icon: const Icon(Icons.lock),
                    label: const Text('CERRAR TURNO Y ARQUEO'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.danger,
                      minimumSize: const Size.fromHeight(44),
                    ),
                  ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Movimientos Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                '💵 MOVIMIENTOS DE CAJA',
                style: TextStyle(
                  fontWeight: FontWeight.w900,
                  color: AppColors.goldAccent,
                  fontSize: 13,
                  letterSpacing: 0.5,
                ),
              ),
              TextButton.icon(
                onPressed: isOpen
                    ? () => _openNuevoMovimientoDialog(staff)
                    : null,
                icon: const Icon(Icons.add_circle, size: 16),
                label: const Text('Registrar'),
              ),
            ],
          ),
          const SizedBox(height: 8),

          if (movimientos.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.all(12),
                child: Text(
                  'No hay movimientos registrados en este turno.',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 12),
                ),
              ),
            )
          else
            ListView.separated(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: movimientos.length,
              separatorBuilder: (_, __) => const SizedBox(height: 6),
              itemBuilder: (context, idx) {
                final m = movimientos[idx];
                final double monto = (m['monto_usd'] is num)
                    ? (m['monto_usd'] as num).toDouble()
                    : 0.0;
                return Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.bgSurface,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppColors.border),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            m['concepto'] ?? 'Movimiento',
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              fontSize: 12,
                            ),
                          ),
                          Text(
                            'Método: ${m['metodo_pago'] ?? "Efectivo"}',
                            style: const TextStyle(
                              color: AppColors.textMuted,
                              fontSize: 10,
                            ),
                          ),
                        ],
                      ),
                      Text(
                        '\$${monto.toStringAsFixed(2)}',
                        style: const TextStyle(
                          fontWeight: FontWeight.w900,
                          color: AppColors.goldAccent,
                          fontSize: 14,
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
        ],
      ),
    );
  }
}
