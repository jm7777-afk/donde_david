import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/mesa.dart';
import '../../providers/staff_provider.dart';
import '../../widgets/donde_david_card.dart';
import '../../widgets/status_badge.dart';

class WaiterScreen extends StatefulWidget {
  final StaffProvider? provider;

  const WaiterScreen({super.key, this.provider});

  @override
  State<WaiterScreen> createState() => _WaiterScreenState();
}

class _WaiterScreenState extends State<WaiterScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _openCambiarMesaDialog(int orderId, StaffProvider staff) {
    final ctrl = TextEditingController(text: '2');
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.bgSurface,
        title: Text(
          'Reasignar Pedido #$orderId',
          style: const TextStyle(
            fontWeight: FontWeight.w900,
            color: Colors.white,
          ),
        ),
        content: TextField(
          controller: ctrl,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(
            labelText: 'Número de Nueva Mesa',
            hintText: '2',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () async {
              final newMesa = int.tryParse(ctrl.text.trim()) ?? 1;
              final ok = await staff.cambiarMesaPedido(orderId, newMesa);
              if (mounted) {
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      ok
                          ? '¡Mesa cambiada exitosamente a #$newMesa!'
                          : staff.errorMessage ?? 'Error al cambiar mesa',
                    ),
                  ),
                );
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.brandOrange,
            ),
            child: const Text('Reasignar'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // In our provider hierarchy, we can pass or look up StaffProvider
    final staff = widget.provider;

    return Scaffold(
      appBar: AppBar(
        title: const Row(
          children: [
            Text(
              '🍽️ PANEL DE MESEROS',
              style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
            ),
          ],
        ),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: AppColors.goldAccent,
          labelColor: AppColors.goldAccent,
          unselectedLabelColor: AppColors.textMuted,
          tabs: [
            Tab(text: 'Mesas (${staff?.mesas.length ?? 0})'),
            Tab(text: 'Llamadas (${staff?.solicitudes.length ?? 0})'),
            Tab(text: 'Listos (${staff?.pedidosListos.length ?? 0})'),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => staff?.fetchMesas(),
          ),
        ],
      ),
      body: staff == null
          ? const Center(child: Text('Cargando mesas...'))
          : TabBarView(
              controller: _tabController,
              children: [
                _buildTablesGrid(staff),
                _buildRequestsList(staff),
                _buildReadyOrdersList(staff),
              ],
            ),
    );
  }

  Widget _buildTablesGrid(StaffProvider staff) {
    return RefreshIndicator(
      onRefresh: () => staff.fetchMesas(),
      color: AppColors.goldAccent,
      child: staff.mesas.isEmpty
          ? const Center(child: Text('No hay mesas configuradas'))
          : GridView.builder(
              padding: const EdgeInsets.all(16),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                childAspectRatio: 0.95,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
              ),
              itemCount: staff.mesas.length,
              itemBuilder: (context, index) {
                final mesa = staff.mesas[index];
                return _buildTableCard(mesa, staff);
              },
            ),
    );
  }

  Widget _buildTableCard(Mesa mesa, StaffProvider staff) {
    Color borderColor = AppColors.border;
    if (mesa.isFree) borderColor = AppColors.success;
    if (mesa.isOccupied) borderColor = AppColors.warning;
    if (mesa.isPendingCleaning) borderColor = AppColors.danger;
    if (mesa.isCleaning) borderColor = AppColors.brandBlue;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.bgCard,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: borderColor, width: 1.5),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                mesa.displayName,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                  fontSize: 15,
                ),
              ),
              StatusBadge(status: mesa.estado),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Capacidad: ${mesa.capacidad} personas',
                style: const TextStyle(
                  color: AppColors.textMuted,
                  fontSize: 11,
                ),
              ),
              if (mesa.isOccupied) ...[
                Text(
                  'Ocupada hace: ${mesa.tiempoOcupacionMin} min',
                  style: const TextStyle(
                    color: AppColors.warning,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  'Pedidos activos: ${mesa.pedidosActivos}',
                  style: const TextStyle(
                    color: AppColors.cyanAccent,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ],
          ),

          // Actions
          if (mesa.isPendingCleaning)
            SizedBox(
              width: double.infinity,
              height: 32,
              child: ElevatedButton(
                onPressed: () =>
                    staff.actualizarLimpiezaMesa(mesa.id, 'INICIAR'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.brandBlue,
                  padding: EdgeInsets.zero,
                ),
                child: const Text(
                  'Iniciar Limpieza',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800),
                ),
              ),
            )
          else if (mesa.isCleaning)
            SizedBox(
              width: double.infinity,
              height: 32,
              child: ElevatedButton(
                onPressed: () =>
                    staff.actualizarLimpiezaMesa(mesa.id, 'FINALIZAR'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.success,
                  padding: EdgeInsets.zero,
                ),
                child: const Text(
                  'Liberar Mesa',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800),
                ),
              ),
            )
          else
            const SizedBox.shrink(),
        ],
      ),
    );
  }

  Widget _buildRequestsList(StaffProvider staff) {
    if (staff.solicitudes.isEmpty) {
      return const Center(
        child: Text('No hay solicitudes pendientes del salón 🎉'),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: staff.solicitudes.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final sol = staff.solicitudes[index];
        final isBill = sol.isRequestBill;

        return DondeDavidCard(
          borderColor: isBill ? AppColors.cyanAccent : AppColors.goldAccent,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Icon(
                    isBill ? Icons.receipt_long : Icons.room_service,
                    color: isBill ? AppColors.cyanAccent : AppColors.goldAccent,
                    size: 28,
                  ),
                  const SizedBox(width: 12),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        sol.numeroMesa,
                        style: const TextStyle(
                          fontWeight: FontWeight.w900,
                          color: Colors.white,
                          fontSize: 14,
                        ),
                      ),
                      Text(
                        isBill
                            ? '🧾 Solicita la Cuenta'
                            : '🙋 Llamando al Mesero',
                        style: TextStyle(
                          color: isBill
                              ? AppColors.cyanAccent
                              : AppColors.goldAccent,
                          fontWeight: FontWeight.w800,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              ElevatedButton(
                onPressed: () => staff.atenderSolicitudMesa(sol.id, 'ATENDIDA'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.success,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 8,
                  ),
                ),
                child: const Text(
                  'Atendida',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w900),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildReadyOrdersList(StaffProvider staff) {
    if (staff.pedidosListos.isEmpty) {
      return const Center(
        child: Text('No hay pedidos listos pendientes de entrega.'),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: staff.pedidosListos.length,
      separatorBuilder: (_, __) => const SizedBox(height: 10),
      itemBuilder: (context, index) {
        final p = staff.pedidosListos[index];
        return DondeDavidCard(
          borderColor: AppColors.success,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'PEDIDO #${p.id} · ${p.numeroMesa}',
                    style: const TextStyle(
                      fontWeight: FontWeight.w900,
                      fontSize: 14,
                      color: AppColors.success,
                    ),
                  ),
                  StatusBadge(status: p.estado),
                ],
              ),
              const Divider(height: 14),
              ...p.detalles.map(
                (d) => Text(
                  '• ${d.cantidad}x ${d.productoNombre}',
                  style: const TextStyle(fontSize: 12),
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () => _openCambiarMesaDialog(p.id, staff),
                      icon: const Icon(Icons.swap_horiz, size: 16),
                      label: const Text(
                        'Cambiar',
                        style: TextStyle(fontSize: 11),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    flex: 2,
                    child: ElevatedButton.icon(
                      onPressed: () => staff.entregarPedidoMesa(p.id),
                      icon: const Icon(Icons.done_all, size: 16),
                      label: const Text(
                        'Entregar en Mesa',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.success,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}
