import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../providers/catalog_provider.dart';
import '../../providers/staff_provider.dart';
import '../../widgets/donde_david_card.dart';
import '../../widgets/donde_david_dish_image.dart';
import 'delivery_courier_screen.dart';
import 'kitchen_kds_screen.dart';
import 'pos_cashier_screen.dart';
import 'waiter_screen.dart';

class AdminDashboardScreen extends StatefulWidget {
  final StaffProvider? staffProvider;
  final CatalogProvider? catalogProvider;

  const AdminDashboardScreen({
    super.key,
    this.staffProvider,
    this.catalogProvider,
  });

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  // Search & Filter state for Products tab
  String _productSearch = '';
  int? _selectedCategoryFilter;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 7, vsync: this);
    _loadAllAdminData();
  }

  void _loadAllAdminData() {
    final staff = widget.staffProvider;
    if (staff != null) {
      staff.fetchManagerDashboard();
      staff.fetchAdminProductos();
      staff.fetchAdminCategorias();
      staff.fetchAdminInsumos();
      staff.fetchAdminMesas();
      staff.fetchAdminUsuarios();
      staff.fetchAdminConfiguraciones();
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final staff = widget.staffProvider;

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '⚙️ SUITE ADMINISTRATIVA',
          style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Sincronizar todo',
            onPressed: _loadAllAdminData,
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          indicatorColor: AppColors.goldAccent,
          labelColor: AppColors.goldAccent,
          unselectedLabelColor: AppColors.textMuted,
          tabs: const [
            Tab(icon: Icon(Icons.dashboard_outlined), text: 'Dashboard'),
            Tab(icon: Icon(Icons.fastfood_outlined), text: 'Menú & Platos'),
            Tab(icon: Icon(Icons.category_outlined), text: 'Categorías'),
            Tab(icon: Icon(Icons.inventory_2_outlined), text: 'Inventario'),
            Tab(icon: Icon(Icons.table_bar_outlined), text: 'Mesas & QR'),
            Tab(icon: Icon(Icons.people_outline), text: 'Personal'),
            Tab(icon: Icon(Icons.settings_outlined), text: 'Configuración'),
          ],
        ),
      ),
      body: staff == null
          ? const Center(child: Text('Personal no disponible'))
          : TabBarView(
              controller: _tabController,
              children: [
                _buildDashboardTab(staff),
                _buildProductosTab(staff),
                _buildCategoriasTab(staff),
                _buildInsumosTab(staff),
                _buildMesasTab(staff),
                _buildUsuariosTab(staff),
                _buildConfiguracionTab(staff),
              ],
            ),
    );
  }

  // ==========================================
  // TAB 1: DASHBOARD & TERMINALES
  // ==========================================
  Widget _buildDashboardTab(StaffProvider staff) {
    final kpis = staff.managerDashboard;
    final double ventasHoy = kpis != null && kpis['ventas_hoy'] is num
        ? (kpis['ventas_hoy'] as num).toDouble()
        : 0.0;
    final double ventasAyer = kpis != null && kpis['ventas_ayer'] is num
        ? (kpis['ventas_ayer'] as num).toDouble()
        : 0.0;
    final int pedidosCocina = kpis != null && kpis['pedidos_cocina'] is num
        ? (kpis['pedidos_cocina'] as num).toInt()
        : 0;
    final int pedidosRetrasados =
        kpis != null && kpis['pedidos_demorados_15min'] is num
        ? (kpis['pedidos_demorados_15min'] as num).toInt()
        : 0;
    final int activeDeliveries =
        kpis != null && kpis['deliveries_activos'] is num
        ? (kpis['deliveries_activos'] as num).toInt()
        : 0;
    final int mesasOcupadas = kpis != null && kpis['mesas_ocupadas'] is num
        ? (kpis['mesas_ocupadas'] as num).toInt()
        : 0;
    final int insumosCriticos = kpis != null && kpis['insumos_criticos'] is num
        ? (kpis['insumos_criticos'] as num).toInt()
        : 0;

    return RefreshIndicator(
      onRefresh: () async => staff.fetchManagerDashboard(),
      color: AppColors.goldAccent,
      child: ListView(
        padding: const EdgeInsets.all(14),
        children: [
          // Banner
          DondeDavidCard(
            padding: const EdgeInsets.all(16),
            gradient: const LinearGradient(
              colors: [Color(0x33071A3D), Color(0x220879E8)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderColor: AppColors.brandBlue,
            child: const Row(
              children: [
                Icon(
                  Icons.admin_panel_settings,
                  color: AppColors.electricTeal,
                  size: 36,
                ),
                SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'PANEL INTEGRAL GERENCIAL',
                        style: TextStyle(
                          fontWeight: FontWeight.w900,
                          color: Colors.white,
                          fontSize: 14,
                        ),
                      ),
                      SizedBox(height: 2),
                      Text(
                        'Supervisión global de operaciones, ventas y personal.',
                        style: TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // KPIs Grid
          const Text(
            '📊 INDICADORES OPERATIVOS EN VIVO (CLOUD):',
            style: TextStyle(
              color: AppColors.goldAccent,
              fontWeight: FontWeight.w900,
              fontSize: 12,
              letterSpacing: 0.6,
            ),
          ),
          const SizedBox(height: 10),

          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            childAspectRatio: 1.45,
            children: [
              _buildKpiCard(
                'Ventas Hoy',
                '\$${ventasHoy.toStringAsFixed(2)}',
                Icons.attach_money,
                AppColors.goldAccent,
              ),
              _buildKpiCard(
                'Ventas Ayer',
                '\$${ventasAyer.toStringAsFixed(2)}',
                Icons.history,
                AppColors.textSecondary,
              ),
              _buildKpiCard(
                'Cocina KDS',
                '$pedidosCocina comandas',
                Icons.soup_kitchen,
                AppColors.brandOrange,
              ),
              _buildKpiCard(
                'Demora > 15m',
                '$pedidosRetrasados alertas',
                Icons.warning,
                pedidosRetrasados > 0 ? AppColors.danger : AppColors.success,
              ),
              _buildKpiCard(
                'Deliveries',
                '$activeDeliveries en ruta',
                Icons.two_wheeler,
                AppColors.electricTeal,
              ),
              _buildKpiCard(
                'Mesas Sala',
                '$mesasOcupadas ocupadas',
                Icons.table_bar,
                AppColors.cyanAccent,
              ),
            ],
          ),

          if (insumosCriticos > 0) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: AppColors.danger.withAlpha(25),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.danger),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.inventory_2,
                    color: AppColors.danger,
                    size: 22,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Alerta: Hay $insumosCriticos insumos en nivel crítico de inventario.',
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],

          const SizedBox(height: 20),
          const Text(
            'TERMINALES OPERATIVOS DEL SISTEMA:',
            style: TextStyle(
              color: AppColors.goldAccent,
              fontWeight: FontWeight.w900,
              fontSize: 12,
              letterSpacing: 0.6,
            ),
          ),
          const SizedBox(height: 10),

          _buildModuleTile(
            context: context,
            icon: Icons.point_of_sale,
            title: '💰 Caja POS & Facturación Touch',
            subtitle: 'Cobro rápido, arqueo de turnos y validación Pago Móvil.',
            color: AppColors.goldAccent,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => PosCashierScreen(
                  provider: widget.staffProvider,
                  catalogProvider: widget.catalogProvider,
                ),
              ),
            ),
          ),
          const SizedBox(height: 8),
          _buildModuleTile(
            context: context,
            icon: Icons.soup_kitchen,
            title: '👨‍🍳 Monitor Cocina KDS',
            subtitle:
                'Comandas en tiempo real, colas de preparación y despacho.',
            color: AppColors.brandOrange,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) =>
                    KitchenKdsScreen(provider: widget.staffProvider),
              ),
            ),
          ),
          const SizedBox(height: 8),
          _buildModuleTile(
            context: context,
            icon: Icons.table_bar,
            title: '🍽️ Panel Meseros & Salón',
            subtitle:
                'Distribución de mesas, llamados de clientes y cambio de mesa.',
            color: AppColors.cyanAccent,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => WaiterScreen(provider: widget.staffProvider),
              ),
            ),
          ),
          const SizedBox(height: 8),
          _buildModuleTile(
            context: context,
            icon: Icons.delivery_dining,
            title: '🛵 Delivery & Repartidores',
            subtitle:
                'Despacho de pedidos, baliza GPS en vivo y confirmación OTP.',
            color: AppColors.electricTeal,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) =>
                    DeliveryCourierScreen(provider: widget.staffProvider),
              ),
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  // ==========================================
  // TAB 2: GESTIÓN DE PRODUCTOS & MENÚ
  // ==========================================
  Widget _buildProductosTab(StaffProvider staff) {
    final rawProds = staff.adminProductos;
    final tasaBs = widget.catalogProvider?.tasaCambioBs ?? 52.0;

    final filtered = rawProds.where((p) {
      final name = (p['nombre'] ?? '').toString().toLowerCase();
      if (_productSearch.isNotEmpty &&
          !name.contains(_productSearch.toLowerCase())) {
        return false;
      }
      if (_selectedCategoryFilter != null &&
          p['categoria_id'] != _selectedCategoryFilter) {
        return false;
      }
      return true;
    }).toList();

    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.brandOrange,
        foregroundColor: Colors.black,
        icon: const Icon(Icons.add),
        label: const Text(
          'Nuevo Plato',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        onPressed: () => _openProductFormDialog(context, staff),
      ),
      body: RefreshIndicator(
        onRefresh: () async => staff.fetchAdminProductos(),
        color: AppColors.goldAccent,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 90),
          children: [
            // Search Box
            TextField(
              decoration: InputDecoration(
                prefixIcon: const Icon(
                  Icons.search,
                  color: AppColors.textMuted,
                ),
                hintText: 'Buscar plato o combo...',
                filled: true,
                fillColor: AppColors.bgSurface,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: AppColors.border),
                ),
                contentPadding: const EdgeInsets.symmetric(horizontal: 14),
              ),
              onChanged: (val) => setState(() => _productSearch = val),
            ),
            const SizedBox(height: 10),

            // Category Filter Chips
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  ChoiceChip(
                    label: const Text('Todos'),
                    selected: _selectedCategoryFilter == null,
                    onSelected: (_) =>
                        setState(() => _selectedCategoryFilter = null),
                    selectedColor: AppColors.goldAccent,
                    labelStyle: TextStyle(
                      color: _selectedCategoryFilter == null
                          ? Colors.black
                          : Colors.white,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(width: 6),
                  ...staff.adminCategorias.map((c) {
                    final id = c['id'] as int?;
                    final isSel = _selectedCategoryFilter == id;
                    return Padding(
                      padding: const EdgeInsets.only(right: 6),
                      child: ChoiceChip(
                        label: Text(c['nombre'] ?? ''),
                        selected: isSel,
                        onSelected: (_) =>
                            setState(() => _selectedCategoryFilter = id),
                        selectedColor: AppColors.goldAccent,
                        labelStyle: TextStyle(
                          color: isSel ? Colors.black : Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    );
                  }),
                ],
              ),
            ),
            const SizedBox(height: 14),

            if (staff.adminLoading)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: CircularProgressIndicator(color: AppColors.goldAccent),
                ),
              )
            else if (filtered.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: Text(
                    'No se encontraron platos',
                    style: TextStyle(color: AppColors.textMuted),
                  ),
                ),
              )
            else
              ...filtered.map((prod) {
                final id = prod['id'] as int? ?? 0;
                final nombre = prod['nombre']?.toString() ?? '';
                final precio = (prod['precio'] is num)
                    ? (prod['precio'] as num).toDouble()
                    : 0.0;
                final precioBs = precio * tasaBs;
                final disponible = prod['disponible'] == true;
                final img = prod['imagen_url']?.toString();
                final stock = prod['stock'] ?? 0;

                return Card(
                  color: AppColors.bgCard,
                  margin: const EdgeInsets.only(bottom: 10),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                    side: const BorderSide(color: AppColors.border),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(10),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        // Dish Image
                        DondeDavidDishImage(
                          rawImageUrl: img,
                          productName: nombre,
                          width: 68,
                          height: 68,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        const SizedBox(width: 12),

                        // Info
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                nombre,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w900,
                                  fontSize: 14,
                                  color: Colors.white,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                '\$${precio.toStringAsFixed(2)} • Bs. ${precioBs.toStringAsFixed(1)}',
                                style: const TextStyle(
                                  color: AppColors.goldAccent,
                                  fontWeight: FontWeight.w800,
                                  fontSize: 12,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                'Stock: $stock un. • ${prod['tiempo_preparacion'] ?? 15} min',
                                style: const TextStyle(
                                  color: AppColors.textMuted,
                                  fontSize: 11,
                                ),
                              ),
                            ],
                          ),
                        ),

                        // Switch & Actions
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Switch(
                              value: disponible,
                              activeThumbColor: AppColors.success,
                              inactiveTrackColor: AppColors.danger.withAlpha(
                                80,
                              ),
                              onChanged: (_) async {
                                await staff.toggleProductoDisponibilidad(
                                  id,
                                  disponible,
                                );
                              },
                            ),
                            Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  icon: const Icon(
                                    Icons.edit,
                                    size: 18,
                                    color: AppColors.cyanAccent,
                                  ),
                                  onPressed: () => _openProductFormDialog(
                                    context,
                                    staff,
                                    product: prod,
                                  ),
                                ),
                                IconButton(
                                  icon: const Icon(
                                    Icons.delete_outline,
                                    size: 18,
                                    color: AppColors.danger,
                                  ),
                                  onPressed: () => _confirmDeleteProduct(
                                    context,
                                    staff,
                                    id,
                                    nombre,
                                  ),
                                ),
                              ],
                            ),
                          ],
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

  // ==========================================
  // TAB 3: GESTIÓN DE CATEGORÍAS
  // ==========================================
  Widget _buildCategoriasTab(StaffProvider staff) {
    final cats = staff.adminCategorias;

    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.cyanAccent,
        foregroundColor: Colors.black,
        icon: const Icon(Icons.add),
        label: const Text(
          'Nueva Categoría',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        onPressed: () => _openCategoriaFormDialog(context, staff),
      ),
      body: RefreshIndicator(
        onRefresh: () async => staff.fetchAdminCategorias(),
        color: AppColors.goldAccent,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 90),
          children: [
            const Text(
              'CATEGORÍAS ACTIVAS DEL MENÚ:',
              style: TextStyle(
                color: AppColors.goldAccent,
                fontWeight: FontWeight.w900,
                fontSize: 12,
                letterSpacing: 0.6,
              ),
            ),
            const SizedBox(height: 12),
            if (cats.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: Text(
                    'No hay categorías registradas',
                    style: TextStyle(color: AppColors.textMuted),
                  ),
                ),
              )
            else
              ...cats.map((cat) {
                final id = cat['id'] as int? ?? 0;
                final nombre = cat['nombre']?.toString() ?? '';
                final desc = cat['descripcion']?.toString() ?? '';

                return Card(
                  color: AppColors.bgCard,
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: const BorderSide(color: AppColors.border),
                  ),
                  child: ListTile(
                    leading: const CircleAvatar(
                      backgroundColor: Color(0x3300F5D4),
                      child: Icon(
                        Icons.category,
                        color: AppColors.cyanAccent,
                        size: 20,
                      ),
                    ),
                    title: Text(
                      nombre,
                      style: const TextStyle(
                        fontWeight: FontWeight.w900,
                        color: Colors.white,
                      ),
                    ),
                    subtitle: desc.isNotEmpty
                        ? Text(
                            desc,
                            style: const TextStyle(
                              color: AppColors.textMuted,
                              fontSize: 11,
                            ),
                          )
                        : null,
                    trailing: IconButton(
                      icon: const Icon(
                        Icons.delete_outline,
                        color: AppColors.danger,
                        size: 20,
                      ),
                      onPressed: () =>
                          _confirmDeleteCategoria(context, staff, id, nombre),
                    ),
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }

  // ==========================================
  // TAB 4: GESTIÓN DE INSUMOS & INVENTARIO
  // ==========================================
  Widget _buildInsumosTab(StaffProvider staff) {
    final insumos = staff.adminInsumos;

    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.goldAccent,
        foregroundColor: Colors.black,
        icon: const Icon(Icons.add_shopping_cart),
        label: const Text(
          'Nuevo Insumo',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        onPressed: () => _openInsumoFormDialog(context, staff),
      ),
      body: RefreshIndicator(
        onRefresh: () async => staff.fetchAdminInsumos(),
        color: AppColors.goldAccent,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 90),
          children: [
            const Text(
              'CONTROL DE STOCK & INGREDIENTES:',
              style: TextStyle(
                color: AppColors.goldAccent,
                fontWeight: FontWeight.w900,
                fontSize: 12,
                letterSpacing: 0.6,
              ),
            ),
            const SizedBox(height: 12),
            if (insumos.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: Text(
                    'No hay insumos registrados',
                    style: TextStyle(color: AppColors.textMuted),
                  ),
                ),
              )
            else
              ...insumos.map((ins) {
                final id = ins['id'] as int? ?? 0;
                final nombre = ins['nombre']?.toString() ?? '';
                final stockActual = (ins['stock_actual'] is num)
                    ? (ins['stock_actual'] as num).toDouble()
                    : 0.0;
                final stockMin = (ins['stock_minimo'] is num)
                    ? (ins['stock_minimo'] as num).toDouble()
                    : 0.0;
                final unidad = ins['unidad_medida']?.toString() ?? 'un';
                final isCritico = stockActual <= stockMin;

                return Card(
                  color: AppColors.bgCard,
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(
                      color: isCritico ? AppColors.danger : AppColors.border,
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        Icon(
                          isCritico
                              ? Icons.warning_amber_rounded
                              : Icons.check_circle_outline,
                          color: isCritico
                              ? AppColors.danger
                              : AppColors.success,
                          size: 26,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                nombre,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w900,
                                  fontSize: 13,
                                  color: Colors.white,
                                ),
                              ),
                              const SizedBox(height: 3),
                              Text(
                                'Stock: ${stockActual.toStringAsFixed(1)} $unidad (Mínimo: ${stockMin.toStringAsFixed(1)} $unidad)',
                                style: TextStyle(
                                  color: isCritico
                                      ? AppColors.danger
                                      : AppColors.textMuted,
                                  fontSize: 11,
                                  fontWeight: isCritico
                                      ? FontWeight.w800
                                      : FontWeight.w500,
                                ),
                              ),
                            ],
                          ),
                        ),
                        ElevatedButton.icon(
                          icon: const Icon(Icons.add, size: 14),
                          label: const Text(
                            'Ingreso',
                            style: TextStyle(fontSize: 11),
                          ),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppColors.electricTeal,
                            foregroundColor: Colors.black,
                            padding: const EdgeInsets.symmetric(
                              horizontal: 10,
                              vertical: 4,
                            ),
                          ),
                          onPressed: () => _openRegistrarIngresoDialog(
                            context,
                            staff,
                            id,
                            nombre,
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

  // ==========================================
  // TAB 5: GESTIÓN DE MESAS & CÓDIGOS QR
  // ==========================================
  Widget _buildMesasTab(StaffProvider staff) {
    final mesas = staff.adminMesas;

    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.cyanAccent,
        foregroundColor: Colors.black,
        icon: const Icon(Icons.add),
        label: const Text(
          'Agregar Mesa',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        onPressed: () => _openMesaFormDialog(context, staff),
      ),
      body: RefreshIndicator(
        onRefresh: () async => staff.fetchAdminMesas(),
        color: AppColors.goldAccent,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 90),
          children: [
            const Text(
              'PLANO DE MESAS DEL SALÓN (CONFIGURACIÓN):',
              style: TextStyle(
                color: AppColors.goldAccent,
                fontWeight: FontWeight.w900,
                fontSize: 12,
                letterSpacing: 0.6,
              ),
            ),
            const SizedBox(height: 12),
            if (mesas.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: Text(
                    'No hay mesas configuradas',
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
                  childAspectRatio: 1.25,
                  crossAxisSpacing: 10,
                  mainAxisSpacing: 10,
                ),
                itemCount: mesas.length,
                itemBuilder: (context, idx) {
                  final m = mesas[idx];
                  final num = m['numero_mesa'] ?? (idx + 1);
                  final cap = m['capacidad'] ?? 4;
                  final estado = m['estado']?.toString() ?? 'LIBRE';

                  return Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.bgCard,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Mesa #$num',
                              style: const TextStyle(
                                fontWeight: FontWeight.w900,
                                fontSize: 14,
                                color: Colors.white,
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 6,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: estado == 'LIBRE'
                                    ? AppColors.success.withAlpha(30)
                                    : AppColors.brandOrange.withAlpha(30),
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Text(
                                estado,
                                style: TextStyle(
                                  color: estado == 'LIBRE'
                                      ? AppColors.success
                                      : AppColors.brandOrange,
                                  fontSize: 9,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                            ),
                          ],
                        ),
                        Text(
                          'Capacidad: $cap personas',
                          style: const TextStyle(
                            color: AppColors.textMuted,
                            fontSize: 11,
                          ),
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            IconButton(
                              icon: const Icon(
                                Icons.qr_code_2,
                                color: AppColors.goldAccent,
                                size: 22,
                              ),
                              tooltip: 'Ver QR de Mesa',
                              onPressed: () =>
                                  _showMesaQrDialog(context, num as int),
                            ),
                            IconButton(
                              icon: const Icon(
                                Icons.delete_outline,
                                color: AppColors.danger,
                                size: 20,
                              ),
                              tooltip: 'Eliminar Mesa',
                              onPressed: () => _confirmDeleteMesa(
                                context,
                                staff,
                                num as int,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  );
                },
              ),
          ],
        ),
      ),
    );
  }

  // ==========================================
  // TAB 6: GESTIÓN DE PERSONAL & USUARIOS
  // ==========================================
  Widget _buildUsuariosTab(StaffProvider staff) {
    final users = staff.adminUsuarios;

    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.brandOrange,
        foregroundColor: Colors.black,
        icon: const Icon(Icons.person_add),
        label: const Text(
          'Nuevo Empleado',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        onPressed: () => _openUsuarioFormDialog(context, staff),
      ),
      body: RefreshIndicator(
        onRefresh: () async => staff.fetchAdminUsuarios(),
        color: AppColors.goldAccent,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 90),
          children: [
            const Text(
              'EQUIPO OPERATIVO Y CUENTAS:',
              style: TextStyle(
                color: AppColors.goldAccent,
                fontWeight: FontWeight.w900,
                fontSize: 12,
                letterSpacing: 0.6,
              ),
            ),
            const SizedBox(height: 12),
            if (users.isEmpty)
              const Center(
                child: Padding(
                  padding: EdgeInsets.all(32),
                  child: Text(
                    'No hay usuarios registrados',
                    style: TextStyle(color: AppColors.textMuted),
                  ),
                ),
              )
            else
              ...users.map((u) {
                final id = u['id'] as int? ?? 0;
                final nombre = '${u['nombre'] ?? ''} ${u['apellido'] ?? ''}'
                    .trim();
                final username = u['nombre_usuario']?.toString() ?? '';
                final email = u['email']?.toString() ?? '';
                final rol = u['rol']?.toString().toUpperCase() ?? 'CLIENTE';
                final activo = u['activo'] == true;

                Color roleColor = AppColors.cyanAccent;
                if (rol.contains('ADMIN')) roleColor = AppColors.goldAccent;
                if (rol.contains('CAJA')) roleColor = AppColors.brandOrange;
                if (rol.contains('COCINA')) roleColor = Colors.orangeAccent;
                if (rol.contains('REPARTIDOR'))
                  roleColor = AppColors.electricTeal;

                return Card(
                  color: AppColors.bgCard,
                  margin: const EdgeInsets.only(bottom: 8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: const BorderSide(color: AppColors.border),
                  ),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: roleColor.withAlpha(30),
                      child: Text(
                        rol.isNotEmpty ? rol[0] : '?',
                        style: TextStyle(
                          color: roleColor,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                    ),
                    title: Row(
                      children: [
                        Text(
                          nombre.isNotEmpty ? nombre : username,
                          style: const TextStyle(
                            fontWeight: FontWeight.w900,
                            color: Colors.white,
                            fontSize: 13,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 1,
                          ),
                          decoration: BoxDecoration(
                            color: roleColor.withAlpha(30),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            rol,
                            style: TextStyle(
                              color: roleColor,
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ],
                    ),
                    subtitle: Text(
                      '@$username • $email',
                      style: const TextStyle(
                        color: AppColors.textMuted,
                        fontSize: 11,
                      ),
                    ),
                    trailing: Switch(
                      value: activo,
                      activeThumbColor: AppColors.success,
                      inactiveTrackColor: AppColors.danger.withAlpha(80),
                      onChanged: (val) async {
                        await staff.actualizarUsuarioAdmin(id, {'activo': val});
                      },
                    ),
                  ),
                );
              }),
          ],
        ),
      ),
    );
  }

  // ==========================================
  // TAB 7: CONFIGURACIÓN DEL NEGOCIO
  // ==========================================
  Widget _buildConfiguracionTab(StaffProvider staff) {
    final cfg = staff.adminConfiguraciones;
    final tasaBcv = cfg['tasa_cambio_bs']?.toString() ?? '901.62';
    final deliveryFee = cfg['costo_delivery']?.toString() ?? '2.00';
    final empaqueFee = cfg['costo_empaque']?.toString() ?? '1.00';
    final ivaPercent = cfg['impuesto_porcentaje']?.toString() ?? '16.00';
    final pagoMovilBanco =
        cfg['pago_movil_banco']?.toString() ?? '0102 Banco de Venezuela';
    final pagoMovilTelf =
        cfg['pago_movil_telefono']?.toString() ?? '04244179135';
    final pagoMovilRif = cfg['pago_movil_rif']?.toString() ?? 'V-31487291';
    final pagoMovilTitular =
        cfg['pago_movil_titular']?.toString() ?? 'Dónde David';
    final telfContacto =
        cfg['whatsapp_contacto']?.toString() ?? '+58 4112 5554';

    final tasaCtrl = TextEditingController(text: tasaBcv);
    final deliveryCtrl = TextEditingController(text: deliveryFee);
    final empaqueCtrl = TextEditingController(text: empaqueFee);
    final ivaCtrl = TextEditingController(text: ivaPercent);
    final bancoCtrl = TextEditingController(text: pagoMovilBanco);
    final telfPagoCtrl = TextEditingController(text: pagoMovilTelf);
    final rifCtrl = TextEditingController(text: pagoMovilRif);
    final titularCtrl = TextEditingController(text: pagoMovilTitular);
    final whatsappCtrl = TextEditingController(text: telfContacto);

    return RefreshIndicator(
      onRefresh: () async => staff.fetchAdminConfiguraciones(),
      color: AppColors.goldAccent,
      child: ListView(
        padding: const EdgeInsets.all(14),
        children: [
          // Tasa BCV Card
          DondeDavidCard(
            padding: const EdgeInsets.all(14),
            borderColor: AppColors.goldAccent,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      '💵 TASA DE CAMBIO OFICIAL BCV',
                      style: TextStyle(
                        fontWeight: FontWeight.w900,
                        color: AppColors.goldAccent,
                        fontSize: 12,
                      ),
                    ),
                    ElevatedButton.icon(
                      icon: const Icon(Icons.sync, size: 14),
                      label: const Text(
                        'Auto-Sync BCV',
                        style: TextStyle(fontSize: 10),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.goldAccent,
                        foregroundColor: Colors.black,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                      ),
                      onPressed: () async {
                        final ok = await staff.sincronizarTasaBcvOficial();
                        if (mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(
                                ok
                                    ? '¡Tasa BCV sincronizada con éxito!'
                                    : 'Error al sincronizar',
                              ),
                            ),
                          );
                        }
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: tasaCtrl,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Tasa Manual (Bs. por 1 USD)',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.brandOrange,
                        foregroundColor: Colors.black,
                      ),
                      onPressed: () async {
                        final val = double.tryParse(tasaCtrl.text) ?? 0.0;
                        if (val > 0) {
                          await staff.actualizarTasaBcvManual(val);
                          if (mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text('Tasa actualizada correctamente'),
                              ),
                            );
                          }
                        }
                      },
                      child: const Text('Guardar'),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Business Settings Form
          DondeDavidCard(
            padding: const EdgeInsets.all(14),
            borderColor: AppColors.border,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '⚙️ PARÁMETROS COMERCIALES',
                  style: TextStyle(
                    fontWeight: FontWeight.w900,
                    color: Colors.white,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: deliveryCtrl,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Costo Delivery Estándar (\$ USD)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: empaqueCtrl,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Costo Empaque para Llevar (\$ USD)',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: ivaCtrl,
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  decoration: const InputDecoration(
                    labelText: 'Impuesto IVA (%)',
                    border: OutlineInputBorder(),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Pago Móvil Data
          DondeDavidCard(
            padding: const EdgeInsets.all(14),
            borderColor: AppColors.cyanAccent,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '📱 DATOS PAGO MÓVIL (PÚBLICOS)',
                  style: TextStyle(
                    fontWeight: FontWeight.w900,
                    color: AppColors.cyanAccent,
                    fontSize: 12,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: bancoCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Banco Emisor',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: telfPagoCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Teléfono Pago Móvil',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: rifCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Cédula / RIF',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: titularCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Titular de Cuenta',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: whatsappCtrl,
                  decoration: const InputDecoration(
                    labelText: 'WhatsApp Oficial de Pedidos',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.cyanAccent,
                      foregroundColor: Colors.black,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    onPressed: () async {
                      final ok = await staff.guardarConfiguracionesLote({
                        'costo_delivery': deliveryCtrl.text.trim(),
                        'costo_empaque': empaqueCtrl.text.trim(),
                        'impuesto_porcentaje': ivaCtrl.text.trim(),
                        'pago_movil_banco': bancoCtrl.text.trim(),
                        'pago_movil_telefono': telfPagoCtrl.text.trim(),
                        'pago_movil_rif': rifCtrl.text.trim(),
                        'pago_movil_titular': titularCtrl.text.trim(),
                        'whatsapp_contacto': whatsappCtrl.text.trim(),
                      });
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              ok
                                  ? '¡Configuración guardada exitosamente!'
                                  : 'Error al guardar',
                            ),
                          ),
                        );
                      }
                    },
                    child: const Text(
                      'GUARDAR PARÁMETROS COMERCIALES',
                      style: TextStyle(fontWeight: FontWeight.w900),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 30),
        ],
      ),
    );
  }

  // ==========================================
  // DIALOGS & FORMS
  // ==========================================
  void _openProductFormDialog(
    BuildContext context,
    StaffProvider staff, {
    dynamic product,
  }) {
    final isEdit = product != null;
    final id = isEdit ? (product['id'] as int? ?? 0) : 0;

    final nombreCtrl = TextEditingController(
      text: isEdit ? product['nombre'] : '',
    );
    final descCtrl = TextEditingController(
      text: isEdit ? product['descripcion'] : '',
    );
    final precioCtrl = TextEditingController(
      text: isEdit ? (product['precio']?.toString() ?? '') : '',
    );
    final precioPromoCtrl = TextEditingController(
      text: isEdit ? (product['precio_promocion']?.toString() ?? '') : '',
    );
    final stockCtrl = TextEditingController(
      text: isEdit ? (product['stock']?.toString() ?? '50') : '50',
    );
    final pointsCtrl = TextEditingController(
      text: isEdit ? (product['puntos_fidelidad']?.toString() ?? '10') : '10',
    );
    final prepCtrl = TextEditingController(
      text: isEdit ? (product['tiempo_preparacion']?.toString() ?? '15') : '15',
    );
    final imgCtrl = TextEditingController(
      text: isEdit ? product['imagen_url'] : '',
    );

    int selectedCatId = isEdit && product['categoria_id'] != null
        ? product['categoria_id']
        : (staff.adminCategorias.isNotEmpty
              ? staff.adminCategorias[0]['id']
              : 1);

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.bgSurface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => Padding(
          padding: EdgeInsets.only(
            left: 16,
            right: 16,
            top: 20,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
          ),
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  isEdit ? 'Editar Plato #$id' : 'Crear Nuevo Plato',
                  style: const TextStyle(
                    fontWeight: FontWeight.w900,
                    fontSize: 16,
                    color: AppColors.goldAccent,
                  ),
                ),
                const SizedBox(height: 14),

                TextField(
                  controller: nombreCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Nombre del Plato *',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),

                // Category selector
                DropdownButtonFormField<int>(
                  initialValue: selectedCatId,
                  decoration: const InputDecoration(
                    labelText: 'Categoría',
                    border: OutlineInputBorder(),
                  ),
                  dropdownColor: AppColors.bgSurface,
                  items: staff.adminCategorias
                      .map(
                        (c) => DropdownMenuItem<int>(
                          value: c['id'] as int?,
                          child: Text(
                            c['nombre']?.toString() ?? '',
                            style: const TextStyle(color: Colors.white),
                          ),
                        ),
                      )
                      .toList(),
                  onChanged: (val) {
                    if (val != null) {
                      setModalState(() => selectedCatId = val);
                    }
                  },
                ),
                const SizedBox(height: 10),

                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: precioCtrl,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Precio USD *',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextField(
                        controller: precioPromoCtrl,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        decoration: const InputDecoration(
                          labelText: 'Precio Promo USD',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),

                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: stockCtrl,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Stock Inicial',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextField(
                        controller: prepCtrl,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'Tiempo Prep (min)',
                          border: OutlineInputBorder(),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),

                TextField(
                  controller: descCtrl,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    labelText: 'Descripción / Ingredientes',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 10),

                TextField(
                  controller: imgCtrl,
                  decoration: const InputDecoration(
                    labelText: 'URL de Imagen (HTTPS)',
                    hintText: 'https://images.unsplash.com/...',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 16),

                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.brandOrange,
                      foregroundColor: Colors.black,
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                    onPressed: () async {
                      final nombre = nombreCtrl.text.trim();
                      final precio = double.tryParse(precioCtrl.text) ?? 0.0;
                      if (nombre.isEmpty || precio <= 0) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Por favor completa nombre y precio'),
                          ),
                        );
                        return;
                      }

                      final promoVal = double.tryParse(precioPromoCtrl.text);

                      final payload = {
                        'nombre': nombre,
                        'descripcion': descCtrl.text.trim(),
                        'precio': precio,
                        'precio_promocion': promoVal != null && promoVal > 0
                            ? promoVal
                            : null,
                        'categoria_id': selectedCatId,
                        'stock': int.tryParse(stockCtrl.text) ?? 50,
                        'tiempo_preparacion': int.tryParse(prepCtrl.text) ?? 15,
                        'puntos_fidelidad': int.tryParse(pointsCtrl.text) ?? 10,
                        'imagen_url': imgCtrl.text.trim().isNotEmpty
                            ? imgCtrl.text.trim()
                            : null,
                        'disponible': true,
                      };

                      bool ok;
                      if (isEdit) {
                        ok = await staff.actualizarProductoAdmin(id, payload);
                      } else {
                        ok = await staff.crearProductoAdmin(payload);
                      }

                      if (mounted) {
                        Navigator.pop(ctx);
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              ok
                                  ? (isEdit
                                        ? '¡Plato actualizado con éxito!'
                                        : '¡Plato creado con éxito!')
                                  : staff.errorMessage ?? 'Error al guardar',
                            ),
                          ),
                        );
                      }
                    },
                    child: Text(
                      isEdit ? 'GUARDAR CAMBIOS' : 'CREAR PLATO',
                      style: const TextStyle(fontWeight: FontWeight.w900),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _confirmDeleteProduct(
    BuildContext context,
    StaffProvider staff,
    int id,
    String name,
  ) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: const Text(
          'Eliminar Plato',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        content: Text('¿Estás seguro de que deseas eliminar "$name"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () async {
              Navigator.pop(context);
              final ok = await staff.eliminarProductoAdmin(id);
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok ? 'Plato eliminado' : staff.errorMessage ?? 'Error',
                    ),
                  ),
                );
              }
            },
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
  }

  void _openCategoriaFormDialog(BuildContext context, StaffProvider staff) {
    final nombreCtrl = TextEditingController();
    final descCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: const Text(
          'Nueva Categoría',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nombreCtrl,
              decoration: const InputDecoration(
                labelText: 'Nombre *',
                hintText: 'HAMBURGUESAS',
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: descCtrl,
              decoration: const InputDecoration(
                labelText: 'Descripción',
                hintText: 'Carnes 100% res',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.cyanAccent,
              foregroundColor: Colors.black,
            ),
            onPressed: () async {
              final nombre = nombreCtrl.text.trim();
              if (nombre.isEmpty) return;
              Navigator.pop(ctx);
              final ok = await staff.crearCategoriaAdmin(
                nombre,
                descCtrl.text.trim(),
              );
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok ? 'Categoría creada' : staff.errorMessage ?? 'Error',
                    ),
                  ),
                );
              }
            },
            child: const Text('Crear'),
          ),
        ],
      ),
    );
  }

  void _confirmDeleteCategoria(
    BuildContext context,
    StaffProvider staff,
    int id,
    String name,
  ) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: const Text(
          'Eliminar Categoría',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        content: Text('¿Deseas eliminar la categoría "$name"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () async {
              Navigator.pop(context);
              final ok = await staff.eliminarCategoriaAdmin(id);
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok
                          ? 'Categoría eliminada'
                          : staff.errorMessage ?? 'Error',
                    ),
                  ),
                );
              }
            },
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
  }

  void _openInsumoFormDialog(BuildContext context, StaffProvider staff) {
    final nombreCtrl = TextEditingController();
    final stockCtrl = TextEditingController(text: '10');
    final minCtrl = TextEditingController(text: '5');
    String unidad = 'kg';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: AppColors.bgSurface,
          title: const Text(
            'Nuevo Insumo',
            style: TextStyle(fontWeight: FontWeight.w900),
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: nombreCtrl,
                decoration: const InputDecoration(
                  labelText: 'Nombre del Insumo *',
                  hintText: 'Queso Cheddar',
                ),
              ),
              const SizedBox(height: 10),
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: stockCtrl,
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      decoration: const InputDecoration(
                        labelText: 'Stock Inicial',
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: TextField(
                      controller: minCtrl,
                      keyboardType: const TextInputType.numberWithOptions(
                        decimal: true,
                      ),
                      decoration: const InputDecoration(
                        labelText: 'Stock Mínimo',
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              DropdownButtonFormField<String>(
                initialValue: unidad,
                decoration: const InputDecoration(
                  labelText: 'Unidad de Medida',
                ),
                dropdownColor: AppColors.bgSurface,
                items: ['kg', 'gr', 'un', 'lts', 'paquete']
                    .map(
                      (u) => DropdownMenuItem(
                        value: u,
                        child: Text(
                          u,
                          style: const TextStyle(color: Colors.white),
                        ),
                      ),
                    )
                    .toList(),
                onChanged: (val) {
                  if (val != null) setDialogState(() => unidad = val);
                },
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.goldAccent,
                foregroundColor: Colors.black,
              ),
              onPressed: () async {
                final nombre = nombreCtrl.text.trim();
                final stock = double.tryParse(stockCtrl.text) ?? 0.0;
                final min = double.tryParse(minCtrl.text) ?? 0.0;
                if (nombre.isEmpty) return;
                Navigator.pop(ctx);
                final ok = await staff.crearInsumoAdmin(
                  nombre: nombre,
                  stock: stock,
                  stockMinimo: min,
                  unidad: unidad,
                );
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        ok ? 'Insumo creado' : staff.errorMessage ?? 'Error',
                      ),
                    ),
                  );
                }
              },
              child: const Text('Guardar'),
            ),
          ],
        ),
      ),
    );
  }

  void _openRegistrarIngresoDialog(
    BuildContext context,
    StaffProvider staff,
    int insumoId,
    String nombre,
  ) {
    final cantCtrl = TextEditingController();
    final costoCtrl = TextEditingController();
    final provCtrl = TextEditingController(text: 'Distribuidor Local');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: Text(
          'Ingreso de Stock: $nombre',
          style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 15),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: cantCtrl,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Cantidad a ingresar *',
                hintText: '10.5',
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: costoCtrl,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Costo Total (\$ USD) *',
                hintText: '25.00',
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: provCtrl,
              decoration: const InputDecoration(labelText: 'Proveedor'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.electricTeal,
              foregroundColor: Colors.black,
            ),
            onPressed: () async {
              final cant = double.tryParse(cantCtrl.text) ?? 0.0;
              final costo = double.tryParse(costoCtrl.text) ?? 0.0;
              if (cant <= 0) return;
              Navigator.pop(ctx);
              final ok = await staff.registrarIngresoInsumoAdmin(
                insumoId: insumoId,
                cantidad: cant,
                costoTotal: costo,
                proveedor: provCtrl.text.trim(),
              );
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok
                          ? 'Stock actualizado exitosamente'
                          : staff.errorMessage ?? 'Error',
                    ),
                  ),
                );
              }
            },
            child: const Text('Registrar'),
          ),
        ],
      ),
    );
  }

  void _openMesaFormDialog(BuildContext context, StaffProvider staff) {
    final numCtrl = TextEditingController();
    final capCtrl = TextEditingController(text: '4');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: const Text(
          'Nueva Mesa',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: numCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Número de Mesa *',
                hintText: '21',
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              controller: capCtrl,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(
                labelText: 'Capacidad de Comensales',
                hintText: '4',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.cyanAccent,
              foregroundColor: Colors.black,
            ),
            onPressed: () async {
              final num = int.tryParse(numCtrl.text) ?? 0;
              final cap = int.tryParse(capCtrl.text) ?? 4;
              if (num <= 0) return;
              Navigator.pop(ctx);
              final ok = await staff.crearMesaAdmin(
                numeroMesa: num,
                capacidad: cap,
              );
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok ? 'Mesa #$num creada' : staff.errorMessage ?? 'Error',
                    ),
                  ),
                );
              }
            },
            child: const Text('Crear'),
          ),
        ],
      ),
    );
  }

  void _showMesaQrDialog(BuildContext context, int mesaNum) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: Text(
          'Código QR: Mesa #$mesaNum',
          style: const TextStyle(fontWeight: FontWeight.w900),
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
              ),
              child: const Icon(
                Icons.qr_code_2,
                size: 160,
                color: Colors.black,
              ),
            ),
            const SizedBox(height: 14),
            Text(
              'Token: QR_DONDE_DAVID_MESA_$mesaNum',
              style: const TextStyle(
                fontWeight: FontWeight.w700,
                fontSize: 12,
                color: AppColors.goldAccent,
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Los comensales pueden escanear este código físico para vincular sus pedidos a esta mesa.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textMuted, fontSize: 11),
            ),
          ],
        ),
        actions: [
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.goldAccent,
              foregroundColor: Colors.black,
            ),
            onPressed: () => Navigator.pop(context),
            child: const Text('Cerrar'),
          ),
        ],
      ),
    );
  }

  void _confirmDeleteMesa(
    BuildContext context,
    StaffProvider staff,
    int numeroMesa,
  ) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: const Text(
          'Eliminar Mesa',
          style: TextStyle(fontWeight: FontWeight.w900),
        ),
        content: Text('¿Deseas eliminar la Mesa #$numeroMesa?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.danger),
            onPressed: () async {
              Navigator.pop(context);
              final ok = await staff.eliminarMesaAdmin(numeroMesa);
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok ? 'Mesa eliminada' : staff.errorMessage ?? 'Error',
                    ),
                  ),
                );
              }
            },
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
  }

  void _openUsuarioFormDialog(BuildContext context, StaffProvider staff) {
    final nomCtrl = TextEditingController();
    final apeCtrl = TextEditingController();
    final userCtrl = TextEditingController();
    final emailCtrl = TextEditingController();
    final telCtrl = TextEditingController();
    final pwdCtrl = TextEditingController(text: 'empleado12345');
    String rol = 'mesero';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: AppColors.bgSurface,
          title: const Text(
            'Nuevo Empleado / Personal',
            style: TextStyle(fontWeight: FontWeight.w900, fontSize: 15),
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nomCtrl,
                  decoration: const InputDecoration(labelText: 'Nombre *'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: apeCtrl,
                  decoration: const InputDecoration(labelText: 'Apellido *'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: userCtrl,
                  decoration: const InputDecoration(labelText: 'Usuario *'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: emailCtrl,
                  keyboardType: TextInputType.emailAddress,
                  decoration: const InputDecoration(labelText: 'Email *'),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: telCtrl,
                  decoration: const InputDecoration(labelText: 'Teléfono'),
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  initialValue: rol,
                  decoration: const InputDecoration(
                    labelText: 'Rol del Empleado',
                  ),
                  dropdownColor: AppColors.bgSurface,
                  items:
                      [
                            'admin',
                            'supervisor',
                            'gerente',
                            'caja',
                            'cocina',
                            'mesero',
                            'repartidor',
                          ]
                          .map(
                            (r) => DropdownMenuItem(
                              value: r,
                              child: Text(
                                r.toUpperCase(),
                                style: const TextStyle(color: Colors.white),
                              ),
                            ),
                          )
                          .toList(),
                  onChanged: (val) {
                    if (val != null) setDialogState(() => rol = val);
                  },
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: pwdCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Contraseña (mín 12 carac) *',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.brandOrange,
                foregroundColor: Colors.black,
              ),
              onPressed: () async {
                final nom = nomCtrl.text.trim();
                final ape = apeCtrl.text.trim();
                final user = userCtrl.text.trim();
                final email = emailCtrl.text.trim();
                final pwd = pwdCtrl.text.trim();

                if (nom.isEmpty ||
                    user.isEmpty ||
                    email.isEmpty ||
                    pwd.length < 12) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text(
                        'Verifica los campos (Contraseña mín 12 caracteres)',
                      ),
                    ),
                  );
                  return;
                }

                Navigator.pop(ctx);
                final ok = await staff.crearUsuarioAdmin({
                  'nombre': nom,
                  'apellido': ape,
                  'nombre_usuario': user,
                  'email': email,
                  'telefono': telCtrl.text.trim(),
                  'password': pwd,
                  'rol': rol,
                  'activo': true,
                });

                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        ok
                            ? 'Empleado creado con éxito'
                            : staff.errorMessage ?? 'Error',
                      ),
                    ),
                  );
                }
              },
              child: const Text('Crear Empleado'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildKpiCard(String title, String val, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: AppColors.textMuted,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
              Icon(icon, size: 16, color: color),
            ],
          ),
          Text(
            val,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w900,
              fontSize: 17,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildModuleTile({
    required BuildContext context,
    required IconData icon,
    required String title,
    required String subtitle,
    required Color color,
    required VoidCallback onTap,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: ListTile(
        onTap: onTap,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
        leading: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: color.withAlpha(30),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: color.withAlpha(80)),
          ),
          child: Icon(icon, color: color, size: 24),
        ),
        title: Text(
          title,
          style: const TextStyle(
            fontWeight: FontWeight.w900,
            fontSize: 13,
            color: Colors.white,
          ),
        ),
        subtitle: Text(
          subtitle,
          style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
        ),
        trailing: const Icon(
          Icons.chevron_right,
          color: AppColors.textMuted,
          size: 18,
        ),
      ),
    );
  }
}
