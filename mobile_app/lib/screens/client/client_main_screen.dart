import 'package:flutter/material.dart';
import '../../core/services/storage_service.dart';
import '../../core/theme/app_colors.dart';
import '../../models/pedido.dart';
import '../../providers/auth_provider.dart';
import '../../providers/cart_provider.dart';
import '../../providers/catalog_provider.dart';
import '../../providers/order_provider.dart';
import '../../providers/staff_provider.dart';
import '../../widgets/brand_header.dart';
import '../../widgets/floating_cart_widget.dart';
import '../../widgets/qr_scanner_dialog.dart';
import '../../widgets/server_config_dialog.dart';
import '../staff/staff_login_screen.dart';
import 'cart_tab.dart';
import 'home_tab.dart';
import 'menu_tab.dart';
import 'order_history_tab.dart';
import 'profile_tab.dart';

class ClientMainScreen extends StatefulWidget {
  final StorageService storage;
  final CatalogProvider catalog;
  final CartProvider cart;
  final AuthProvider auth;
  final OrderProvider order;
  final StaffProvider staff;

  const ClientMainScreen({
    super.key,
    required this.storage,
    required this.catalog,
    required this.cart,
    required this.auth,
    required this.order,
    required this.staff,
  });

  @override
  State<ClientMainScreen> createState() => _ClientMainScreenState();
}

class _ClientMainScreenState extends State<ClientMainScreen> {
  int _currentTabIndex = 0;

  void _openQrScanner() {
    showDialog(
      context: context,
      builder: (_) => QrScannerDialog(
        currentTable: widget.catalog.activeTable,
        onTableSelected: (table) => widget.catalog.setActiveTable(table),
        onClearTable: () => widget.catalog.clearActiveTable(),
      ),
    );
  }

  void _openServerConfig() {
    showDialog(
      context: context,
      builder: (_) => ServerConfigDialog(
        storage: widget.storage,
        onSaved: () {
          widget.catalog.loadCatalog();
        },
      ),
    );
  }

  void _openStaffPortal() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => StaffLoginScreen(
          auth: widget.auth,
          catalog: widget.catalog,
          staff: widget.staff,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    // 5 main view tabs
    final views = [
      HomeTab(
        catalog: widget.catalog,
        cart: widget.cart,
        auth: widget.auth,
        order: widget.order,
        onGoToMenu: () => setState(() => _currentTabIndex = 1),
        onOpenQrModal: _openQrScanner,
        onOpenLoginModal: () => setState(() => _currentTabIndex = 4),
      ),
      MenuTab(catalog: widget.catalog, cart: widget.cart),
      CartTab(
        cart: widget.cart,
        catalog: widget.catalog,
        order: widget.order,
        onGoToMenu: () => setState(() => _currentTabIndex = 1),
      ),
      OrderHistoryTab(
        order: widget.order,
        catalog: widget.catalog,
        cart: widget.cart,
        onTrackOrder: (Pedido p) {
          widget.order.setTrackedOrder(p);
          setState(() => _currentTabIndex = 2);
        },
        onGoToMenu: () => setState(() => _currentTabIndex = 1),
      ),
      ProfileTab(auth: widget.auth),
    ];

    final double totalBs = widget.cart.subtotal * widget.catalog.tasaCambioBs;

    return Scaffold(
      appBar: BrandHeader(
        activeTable: widget.catalog.activeTable,
        tasaCambioBs: widget.catalog.tasaCambioBs,
        onTableTap: _openQrScanner,
        onSettingsTap: _openServerConfig,
        onStaffPortalTap: _openStaffPortal,
      ),
      body: Stack(
        children: [
          IndexedStack(index: _currentTabIndex, children: views),

          // Floating Cart Pill (Only shown when cart has items and not on cart tab)
          if (_currentTabIndex != 2)
            FloatingCartWidget(
              itemCount: widget.cart.itemCount,
              totalPriceUsd: widget.cart.subtotal,
              totalPriceBs: totalBs,
              onTap: () => setState(() => _currentTabIndex = 2),
            ),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentTabIndex,
        onTap: (index) {
          if (index == 5) {
            _openQrScanner();
          } else {
            setState(() => _currentTabIndex = index);
          }
        },
        items: [
          const BottomNavigationBarItem(
            icon: Icon(Icons.home_outlined),
            activeIcon: Icon(Icons.home, color: AppColors.goldAccent),
            label: 'Inicio',
          ),
          const BottomNavigationBarItem(
            icon: Icon(Icons.restaurant_menu_outlined),
            activeIcon: Icon(
              Icons.restaurant_menu,
              color: AppColors.goldAccent,
            ),
            label: 'Menú',
          ),
          BottomNavigationBarItem(
            icon: Badge(
              isLabelVisible: widget.cart.itemCount > 0,
              label: Text('${widget.cart.itemCount}'),
              backgroundColor: AppColors.brandOrange,
              child: const Icon(Icons.shopping_cart_outlined),
            ),
            activeIcon: Badge(
              isLabelVisible: widget.cart.itemCount > 0,
              label: Text('${widget.cart.itemCount}'),
              backgroundColor: AppColors.brandOrange,
              child: const Icon(
                Icons.shopping_cart,
                color: AppColors.goldAccent,
              ),
            ),
            label: 'Carrito',
          ),
          const BottomNavigationBarItem(
            icon: Icon(Icons.receipt_outlined),
            activeIcon: Icon(Icons.receipt, color: AppColors.goldAccent),
            label: 'Pedidos',
          ),
          const BottomNavigationBarItem(
            icon: Icon(Icons.person_outline),
            activeIcon: Icon(Icons.person, color: AppColors.goldAccent),
            label: 'Perfil',
          ),
        ],
      ),
    );
  }
}
