import 'package:flutter/material.dart';
import '../core/services/storage_service.dart';
import '../core/theme/app_colors.dart';
import '../providers/auth_provider.dart';
import '../providers/cart_provider.dart';
import '../providers/catalog_provider.dart';
import '../providers/order_provider.dart';
import '../providers/staff_provider.dart';
import '../widgets/donde_david_card.dart';
import '../widgets/server_config_dialog.dart';
import 'client/client_main_screen.dart';
import 'staff/admin_dashboard_screen.dart';
import 'staff/delivery_courier_screen.dart';
import 'staff/kitchen_kds_screen.dart';
import 'staff/pos_cashier_screen.dart';
import 'staff/staff_login_screen.dart';
import 'staff/waiter_screen.dart';

class WelcomeGatewayScreen extends StatefulWidget {
  final StorageService storage;
  final CatalogProvider catalog;
  final CartProvider cart;
  final AuthProvider auth;
  final OrderProvider order;
  final StaffProvider staff;

  const WelcomeGatewayScreen({
    super.key,
    required this.storage,
    required this.catalog,
    required this.cart,
    required this.auth,
    required this.order,
    required this.staff,
  });

  @override
  State<WelcomeGatewayScreen> createState() => _WelcomeGatewayScreenState();
}

class _WelcomeGatewayScreenState extends State<WelcomeGatewayScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _scaleAnimation;
  late Animation<double> _fadeAnimation;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _scaleAnimation = CurvedAnimation(
      parent: _animController,
      curve: Curves.easeOutBack,
    );
    _fadeAnimation = CurvedAnimation(
      parent: _animController,
      curve: Curves.easeIn,
    );
    _animController.forward();
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  void _navigateToClient() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ClientMainScreen(
          storage: widget.storage,
          catalog: widget.catalog,
          cart: widget.cart,
          auth: widget.auth,
          order: widget.order,
          staff: widget.staff,
        ),
      ),
    );
  }

  void _navigateToStaffPortal() {
    final user = widget.auth.user;
    if (widget.auth.isAuthenticated && user != null && user.isStaff) {
      // Si ya está autenticado con sesión activa, dirigir directamente a su módulo
      Widget targetScreen;
      switch (user.rol.toLowerCase()) {
        case 'cocina':
          targetScreen = KitchenKdsScreen(provider: widget.staff);
          break;
        case 'caja':
          targetScreen = PosCashierScreen(provider: widget.staff);
          break;
        case 'mesero':
          targetScreen = WaiterScreen(provider: widget.staff);
          break;
        case 'repartidor':
          targetScreen = DeliveryCourierScreen(provider: widget.staff);
          break;
        case 'admin':
        case 'supervisor':
        case 'gerente':
        default:
          targetScreen = AdminDashboardScreen(
            staffProvider: widget.staff,
            catalogProvider: widget.catalog,
          );
      }
      Navigator.push(context, MaterialPageRoute(builder: (_) => targetScreen));
    } else {
      // De lo contrario, abrir pantalla de Login de Staff con Biometría
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => StaffLoginScreen(
            auth: widget.auth,
            staff: widget.staff,
            catalog: widget.catalog,
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final currentBaseUrl = widget.storage.getBaseUrl();
    final isOnline = !widget.catalog.isOffline;
    final tasaBcv = widget.catalog.tasaCambioBs;
    final staffUser = widget.auth.user;
    final isStaffLoggedIn =
        widget.auth.isAuthenticated && staffUser != null && staffUser.isStaff;

    return Scaffold(
      backgroundColor: AppColors.bgMain,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.dns, color: AppColors.goldAccent, size: 22),
            tooltip: 'Configuración de Servidor API',
            onPressed: () => showDialog(
              context: context,
              builder: (_) => ServerConfigDialog(
                storage: widget.storage,
                onSaved: () {
                  setState(() {});
                  widget.catalog.loadCatalog();
                },
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          child: FadeTransition(
            opacity: _fadeAnimation,
            child: ScaleTransition(
              scale: _scaleAnimation,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  // 1. BRAND LOGO & NEON RING
                  Center(
                    child: Container(
                      width: 110,
                      height: 110,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.brandOrange.withAlpha(120),
                            blurRadius: 30,
                            spreadRadius: 4,
                          ),
                          BoxShadow(
                            color: AppColors.goldAccent.withAlpha(80),
                            blurRadius: 15,
                            spreadRadius: 2,
                          ),
                        ],
                        border: Border.all(
                          color: AppColors.goldAccent,
                          width: 2.5,
                        ),
                      ),
                      child: ClipOval(
                        child: Image.asset(
                          'assets/images/logo.png',
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => Image.asset(
                            'assets/images/logo-donde-david.jpg',
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Container(
                              color: AppColors.navyLight,
                              child: const Icon(
                                Icons.fastfood,
                                size: 55,
                                color: AppColors.goldAccent,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),

                  const SizedBox(height: 16),

                  // 2. BRAND TITLE & TAGLINE
                  const Text(
                    'DONDE DAVID',
                    style: TextStyle(
                      fontFamily: 'Montserrat',
                      fontWeight: FontWeight.w900,
                      fontSize: 28,
                      letterSpacing: 2,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.brandOrange.withAlpha(40),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(
                        color: AppColors.brandOrange.withAlpha(150),
                      ),
                    ),
                    child: const Text(
                      '🍔 FAST FOOD & RESTAURANT SYSTEM 2.0',
                      style: TextStyle(
                        color: AppColors.goldAccent,
                        fontWeight: FontWeight.w800,
                        fontSize: 11,
                        letterSpacing: 0.8,
                      ),
                    ),
                  ),

                  const SizedBox(height: 14),

                  // 3. LIVE CLOUD CONNECTION PILL
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.bgSurface,
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(
                        color: isOnline
                            ? AppColors.electricTeal.withAlpha(180)
                            : AppColors.warning,
                      ),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 9,
                          height: 9,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: isOnline
                                ? AppColors.electricTeal
                                : AppColors.warning,
                            boxShadow: [
                              BoxShadow(
                                color:
                                    (isOnline
                                            ? AppColors.electricTeal
                                            : AppColors.warning)
                                        .withAlpha(180),
                                blurRadius: 6,
                                spreadRadius: 1,
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          isOnline
                              ? 'Nube Render Conectada'
                              : 'Modo Offline (Caché Local)',
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontWeight: FontWeight.w700,
                            fontSize: 11,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '· BCV: ${tasaBcv.toStringAsFixed(2)} Bs/\$',
                          style: const TextStyle(
                            color: AppColors.goldAccent,
                            fontWeight: FontWeight.w800,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),

                  const SizedBox(height: 24),

                  // 4. ACTIVE STAFF SESSION NOTIFICATION (If logged in)
                  if (isStaffLoggedIn) ...[
                    DondeDavidCard(
                      borderColor: AppColors.electricTeal,
                      gradient: LinearGradient(
                        colors: [
                          AppColors.electricTeal.withAlpha(40),
                          AppColors.navyLight.withAlpha(100),
                        ],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      child: Row(
                        children: [
                          const Icon(
                            Icons.verified_user,
                            color: AppColors.electricTeal,
                            size: 26,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'Sesión Activa: ${staffUser.nombre} ${staffUser.apellido}',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.w900,
                                    fontSize: 13,
                                  ),
                                ),
                                Text(
                                  'Rol: ${staffUser.rol.toUpperCase()}',
                                  style: const TextStyle(
                                    color: AppColors.goldAccent,
                                    fontWeight: FontWeight.w800,
                                    fontSize: 11,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          TextButton(
                            onPressed: () async {
                              await widget.auth.logout();
                              setState(() {});
                            },
                            child: const Text(
                              'Salir',
                              style: TextStyle(
                                color: AppColors.danger,
                                fontSize: 11,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  // 5. DUAL GATEWAY CHOICE CARDS
                  // GATEWAY CARD 1: CLIENT EXPERIENCE
                  _buildGatewayCard(
                    title: 'EXPERIENCIA CLIENTE & SALÓN',
                    subtitle:
                        'Escanea el código QR de tu mesa, navega nuestro menú interactivo o pide delivery directo a tu ubicación.',
                    badge: 'ACCESO PÚBLICO',
                    icon: Icons.restaurant_menu,
                    primaryColor: AppColors.brandOrange,
                    secondaryColor: AppColors.goldAccent,
                    tags: [
                      '🍔 Menú Digital',
                      '📱 Pedido QR Mesa',
                      '🛵 Delivery con Mapa',
                      '🎁 Puntos',
                    ],
                    actionLabel: 'INGRESAR COMO CLIENTE',
                    onTap: _navigateToClient,
                  ),

                  const SizedBox(height: 18),

                  // GATEWAY CARD 2: STAFF OPERATIONS
                  _buildGatewayCard(
                    title: 'TERMINAL DE PERSONAL & STAFF',
                    subtitle:
                        'Caja POS con facturación, monitor de cocina KDS, garzones de sala, despacho delivery y gerencia.',
                    badge: 'ACCESO AUTORIZADO',
                    icon: Icons.point_of_sale,
                    primaryColor: AppColors.electricTeal,
                    secondaryColor: AppColors.brandBlue,
                    tags: [
                      '💰 Caja POS',
                      '👨‍🍳 Monitor KDS',
                      '🛎️ Garzón',
                      '🛵 Repartidor',
                      '📊 Admin',
                    ],
                    actionLabel: isStaffLoggedIn
                        ? 'ENTRAR A MI PANEL (${staffUser.rol.toUpperCase()})'
                        : 'ACCESO PERSONAL / BIOMETRÍA',
                    onTap: _navigateToStaffPortal,
                  ),

                  const SizedBox(height: 28),

                  // 6. FOOTER
                  Text(
                    'Servidor Conectado: ${currentBaseUrl.replaceAll('https://', '')}',
                    style: const TextStyle(
                      color: AppColors.textMuted,
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'DONDE DAVID Fast Food Enterprise · Valencia, Venezuela',
                    style: TextStyle(color: AppColors.textMuted, fontSize: 10),
                  ),
                  const SizedBox(height: 12),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildGatewayCard({
    required String title,
    required String subtitle,
    required String badge,
    required IconData icon,
    required Color primaryColor,
    required Color secondaryColor,
    required List<String> tags,
    required String actionLabel,
    required VoidCallback onTap,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.bgSurface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: primaryColor.withAlpha(160), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: primaryColor.withAlpha(35),
            blurRadius: 18,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(20),
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: primaryColor.withAlpha(40),
                        borderRadius: BorderRadius.circular(14),
                        border: Border.all(color: primaryColor.withAlpha(120)),
                      ),
                      child: Icon(icon, color: primaryColor, size: 28),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                  vertical: 2,
                                ),
                                decoration: BoxDecoration(
                                  color: primaryColor.withAlpha(30),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  badge,
                                  style: TextStyle(
                                    color: primaryColor,
                                    fontSize: 9,
                                    fontWeight: FontWeight.w900,
                                    letterSpacing: 0.8,
                                  ),
                                ),
                              ),
                              Icon(
                                Icons.arrow_forward,
                                color: primaryColor,
                                size: 18,
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            title,
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w900,
                              fontSize: 15,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 12,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: tags
                      .map(
                        (t) => Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 3,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.bgMain,
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: AppColors.border),
                          ),
                          child: Text(
                            t,
                            style: const TextStyle(
                              color: AppColors.textPrimary,
                              fontSize: 10,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      )
                      .toList(),
                ),
                const SizedBox(height: 14),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [primaryColor, secondaryColor],
                      begin: Alignment.centerLeft,
                      end: Alignment.centerRight,
                    ),
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: primaryColor.withAlpha(80),
                        blurRadius: 8,
                        offset: const Offset(0, 3),
                      ),
                    ],
                  ),
                  child: Center(
                    child: Text(
                      actionLabel,
                      style: const TextStyle(
                        color: Colors.black,
                        fontWeight: FontWeight.w900,
                        fontSize: 12,
                        letterSpacing: 0.8,
                      ),
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
}
