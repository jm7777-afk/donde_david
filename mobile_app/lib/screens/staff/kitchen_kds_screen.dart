import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/pedido.dart';
import '../../providers/staff_provider.dart';
import '../../widgets/donde_david_card.dart';
import '../../widgets/status_badge.dart';

class KitchenKdsScreen extends StatefulWidget {
  final StaffProvider? provider;

  const KitchenKdsScreen({super.key, this.provider});

  @override
  State<KitchenKdsScreen> createState() => _KitchenKdsScreenState();
}

class _KitchenKdsScreenState extends State<KitchenKdsScreen> {
  String _searchQuery = '';
  double _scaleMultiplier = 1.0; // 0.85 = compact, 1.0 = normal, 1.15 = large

  @override
  void initState() {
    super.initState();
    widget.provider?.fetchKitchenOrders();
  }

  @override
  Widget build(BuildContext context) {
    final staff = widget.provider;
    final allOrders = staff?.kitchenOrders ?? [];

    final filteredOrders = allOrders.where((o) {
      if (_searchQuery.isEmpty) return true;
      final q = _searchQuery.toLowerCase();
      final matchId = o.id.toString().contains(q);
      final matchMesa = o.numeroMesa.toLowerCase().contains(q);
      final matchDish = o.detalles.any(
        (d) => d.productoNombre.toLowerCase().contains(q),
      );
      return matchId || matchMesa || matchDish;
    }).toList();

    final recibidos = allOrders
        .where((o) => o.estado == 'PENDIENTE' || o.estado == 'COBRADO')
        .length;
    final preparando = allOrders
        .where((o) => o.estado == 'EN_PREPARACION')
        .length;
    final listos = allOrders.where((o) => o.estado == 'LISTO').length;

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '👨‍🍳 MONITOR KDS DE COCINA',
          style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
        ),
        actions: [
          // Scale selector (Estilo Cashea del sistema web)
          PopupMenuButton<double>(
            icon: const Icon(Icons.zoom_in, color: AppColors.goldAccent),
            tooltip: 'Escala de visualización KDS',
            onSelected: (scale) => setState(() => _scaleMultiplier = scale),
            itemBuilder: (_) => const [
              PopupMenuItem(value: 0.85, child: Text('🔍 Compacto (85%)')),
              PopupMenuItem(value: 1.0, child: Text('📐 Normal (100%)')),
              PopupMenuItem(value: 1.15, child: Text('🐘 Ampliado (115%)')),
            ],
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Actualizar',
            onPressed: () => staff?.fetchKitchenOrders(),
          ),
        ],
      ),
      body: staff == null
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // 1. Live Counters Topbar
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 8,
                  ),
                  color: AppColors.bgSurface,
                  child: Row(
                    children: [
                      _buildCounter('RECIBIDOS', recibidos, AppColors.warning),
                      const SizedBox(width: 8),
                      _buildCounter(
                        'PREPARANDO',
                        preparando,
                        AppColors.brandOrange,
                      ),
                      const SizedBox(width: 8),
                      _buildCounter('LISTOS', listos, AppColors.success),
                    ],
                  ),
                ),

                // 2. Modality & Search Bar
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 8,
                  ),
                  decoration: const BoxDecoration(
                    color: AppColors.bgSurface,
                    border: Border(bottom: BorderSide(color: AppColors.border)),
                  ),
                  child: Column(
                    children: [
                      TextField(
                        onChanged: (val) => setState(() => _searchQuery = val),
                        decoration: InputDecoration(
                          hintText: '🔍 Buscar por comanda, mesa o platillo...',
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
                      const SizedBox(height: 8),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            _buildFilterChip('Todas', null, staff),
                            const SizedBox(width: 6),
                            _buildFilterChip('Mesa', 'mesa', staff),
                            const SizedBox(width: 6),
                            _buildFilterChip('Llevar', 'llevar', staff),
                            const SizedBox(width: 6),
                            _buildFilterChip('Delivery', 'delivery', staff),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                // 3. Comandas Grid / List
                Expanded(
                  child: RefreshIndicator(
                    onRefresh: () => staff.fetchKitchenOrders(),
                    color: AppColors.goldAccent,
                    child: filteredOrders.isEmpty
                        ? const Center(
                            child: Text(
                              'No hay comandas en cola 🎉',
                              style: TextStyle(color: AppColors.textMuted),
                            ),
                          )
                        : ListView.separated(
                            padding: const EdgeInsets.all(14),
                            itemCount: filteredOrders.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 12),
                            itemBuilder: (context, index) {
                              final order = filteredOrders[index];
                              return _buildKitchenOrderCard(order, staff);
                            },
                          ),
                  ),
                ),
              ],
            ),
    );
  }

  Widget _buildCounter(String label, int count, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 6),
        decoration: BoxDecoration(
          color: color.withAlpha(25),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withAlpha(90)),
        ),
        child: Column(
          children: [
            Text(
              '$count',
              style: TextStyle(
                color: color,
                fontSize: 16,
                fontWeight: FontWeight.w900,
              ),
            ),
            Text(
              label,
              style: TextStyle(
                color: color,
                fontSize: 9,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChip(String label, String? tipo, StaffProvider staff) {
    final isSelected = staff.kitchenFilterTipo == tipo;
    return ChoiceChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (_) => staff.setKitchenFilter(tipo),
      selectedColor: AppColors.goldAccent,
      backgroundColor: AppColors.bgMain,
      labelStyle: TextStyle(
        color: isSelected ? Colors.black : AppColors.textSecondary,
        fontWeight: FontWeight.w800,
        fontSize: 11,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
    );
  }

  Widget _buildKitchenOrderCard(Pedido order, StaffProvider staff) {
    final isPrepping = order.estado == 'EN_PREPARACION';
    final isReady = order.estado == 'LISTO';

    // Timer calculation
    final now = DateTime.now();
    final elapsedMin = order.fechaCreacion != null
        ? now.difference(order.fechaCreacion!).inMinutes
        : 0;
    Color timerColor = AppColors.success;
    if (elapsedMin >= 10 && elapsedMin < 15) timerColor = AppColors.warning;
    if (elapsedMin >= 15) timerColor = AppColors.danger;

    Color cardBorder = AppColors.border;
    if (isPrepping) cardBorder = AppColors.brandOrange;
    if (isReady) cardBorder = AppColors.success;

    final fontSizeTitle = 14.0 * _scaleMultiplier;
    final fontSizeDish = 13.0 * _scaleMultiplier;

    return DondeDavidCard(
      borderColor: cardBorder,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Text(
                    '#${order.id}',
                    style: TextStyle(
                      fontWeight: FontWeight.w900,
                      color: AppColors.goldAccent,
                      fontSize: fontSizeTitle + 2,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.electricTeal.withAlpha(20),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: AppColors.electricTeal.withAlpha(90),
                      ),
                    ),
                    child: Text(
                      order.numeroMesa,
                      style: const TextStyle(
                        color: AppColors.electricTeal,
                        fontWeight: FontWeight.w900,
                        fontSize: 11,
                      ),
                    ),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    '(${order.tipo.toUpperCase()})',
                    style: const TextStyle(
                      color: AppColors.textMuted,
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
              // Elapsed Timer Badge
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: timerColor.withAlpha(30),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: timerColor),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.timer, size: 12, color: timerColor),
                    const SizedBox(width: 4),
                    Text(
                      '${elapsedMin}m',
                      style: TextStyle(
                        color: timerColor,
                        fontWeight: FontWeight.w900,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const Divider(height: 14),

          // Dishes in Order
          ...order.detalles.map((d) {
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        '${d.cantidad}x ${d.productoNombre}',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                          fontSize: fontSizeDish,
                        ),
                      ),
                      StatusBadge(status: d.estado),
                    ],
                  ),
                  if (d.personalizaciones.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(
                        d.personalizaciones.entries
                            .map((e) => '• ${e.key}: ${e.value}')
                            .join('\n'),
                        style: const TextStyle(
                          color: AppColors.goldAccent,
                          fontSize: 11,
                        ),
                      ),
                    ),
                  if (d.observaciones != null && d.observaciones!.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Text(
                        'Nota: ${d.observaciones}',
                        style: const TextStyle(
                          color: AppColors.electricTeal,
                          fontSize: 11,
                          fontStyle: FontStyle.italic,
                        ),
                      ),
                    ),
                ],
              ),
            );
          }),

          const Divider(height: 14),

          // KDS Status Flow Actions
          Row(
            children: [
              if (!isPrepping && !isReady)
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () => staff.actualizarEstadoCocina(
                      order.id,
                      'EN_PREPARACION',
                    ),
                    icon: const Icon(Icons.soup_kitchen, size: 16),
                    label: const Text(
                      'INICIAR PREPARACIÓN',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.brandOrange,
                      foregroundColor: Colors.black,
                    ),
                  ),
                )
              else if (isPrepping)
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: () =>
                        staff.actualizarEstadoCocina(order.id, 'LISTO'),
                    icon: const Icon(Icons.check_circle, size: 16),
                    label: const Text(
                      'MARCAR LISTO (DESPACHAR)',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.success,
                    ),
                  ),
                )
              else
                const Expanded(
                  child: Center(
                    child: Text(
                      '✅ Listo para entrega o despacho',
                      style: TextStyle(
                        color: AppColors.success,
                        fontWeight: FontWeight.w800,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
