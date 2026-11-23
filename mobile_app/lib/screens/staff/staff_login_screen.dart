import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../../core/services/biometric_service.dart';
import '../../core/theme/app_colors.dart';
import '../../providers/auth_provider.dart';
import '../../providers/catalog_provider.dart';
import '../../providers/staff_provider.dart';
import '../../widgets/donde_david_button.dart';
import '../../widgets/donde_david_card.dart';
import 'admin_dashboard_screen.dart';
import 'delivery_courier_screen.dart';
import 'kitchen_kds_screen.dart';
import 'pos_cashier_screen.dart';
import 'waiter_screen.dart';

class StaffLoginScreen extends StatefulWidget {
  final AuthProvider auth;
  final CatalogProvider catalog;
  final StaffProvider staff;

  const StaffLoginScreen({
    super.key,
    required this.auth,
    required this.catalog,
    required this.staff,
  });

  @override
  State<StaffLoginScreen> createState() => _StaffLoginScreenState();
}

class _StaffLoginScreenState extends State<StaffLoginScreen> {
  final TextEditingController _userController = TextEditingController();
  final TextEditingController _passController = TextEditingController();
  final BiometricService _biometricService = BiometricService();
  bool _canUseBiometrics = false;

  @override
  void initState() {
    super.initState();
    _checkBiometrics();
  }

  Future<void> _checkBiometrics() async {
    final available = await _biometricService.isBiometricAvailable();
    if (mounted) {
      setState(() => _canUseBiometrics = available);
    }
  }

  Future<void> _loginWithBiometrics() async {
    final username = _userController.text.trim();
    final password = _passController.text;
    if (username.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Ingresa tu usuario y contraseña; la biometría solo confirma el acceso.',
          ),
        ),
      );
      return;
    }

    final authenticated = await _biometricService.authenticate(
      reason: 'Confirma tu identidad para iniciar sesión',
    );
    if (!mounted) return;
    if (authenticated) {
      await _attemptLogin(username, password);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'No se pudo confirmar la biometría. Intenta iniciar sesión con tus credenciales.',
          ),
        ),
      );
    }
  }

  @override
  void dispose() {
    _userController.dispose();
    _passController.dispose();
    super.dispose();
  }

  void _routeByRole(String role) {
    Widget destination;
    switch (role) {
      case 'cocina':
        destination = KitchenKdsScreen(provider: widget.staff);
        break;
      case 'caja':
        destination = PosCashierScreen(
          provider: widget.staff,
          catalogProvider: widget.catalog,
        );
        break;
      case 'mesero':
        destination = WaiterScreen(provider: widget.staff);
        break;
      case 'repartidor':
        destination = DeliveryCourierScreen(provider: widget.staff);
        break;
      case 'admin':
      case 'supervisor':
      case 'gerente':
      default:
        destination = AdminDashboardScreen(
          staffProvider: widget.staff,
          catalogProvider: widget.catalog,
        );
        break;
    }

    Navigator.pushReplacement(
      context,
      MaterialPageRoute(builder: (_) => destination),
    );
  }

  Future<void> _attemptLogin(String username, String password) async {
    final ok = await widget.auth.login(username, password);
    if (ok && mounted) {
      final role = widget.auth.user?.rol ?? 'admin';
      _routeByRole(role);
    } else if (mounted && widget.auth.errorMessage != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(widget.auth.errorMessage!),
          backgroundColor: AppColors.danger,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PORTAL DE PERSONAL'),
        backgroundColor: Colors.transparent,
      ),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 440),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                // Logo & Title
                ClipRRect(
                  borderRadius: BorderRadius.circular(40),
                  child: Container(
                    width: 76,
                    height: 76,
                    decoration: BoxDecoration(
                      border: Border.all(
                        color: AppColors.goldAccent,
                        width: 2.5,
                      ),
                      borderRadius: BorderRadius.circular(40),
                    ),
                    child: Image.asset(
                      'assets/images/logo-donde-david.jpg',
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => const Icon(
                        Icons.restaurant,
                        color: AppColors.goldAccent,
                        size: 40,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'PORTAL DE PERSONAL',
                  style: TextStyle(
                    color: AppColors.goldAccent,
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.8,
                  ),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Ingreso Exclusivo para Empleados y Administradores',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 12),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),

                // Login Form Card
                DondeDavidCard(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    children: [
                      TextField(
                        controller: _userController,
                        decoration: const InputDecoration(
                          labelText: 'Nombre de Usuario',
                          prefixIcon: Icon(
                            Icons.person,
                            color: AppColors.textMuted,
                          ),
                        ),
                        style: const TextStyle(fontSize: 13),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _passController,
                        decoration: const InputDecoration(
                          labelText: 'Contraseña',
                          prefixIcon: Icon(
                            Icons.lock,
                            color: AppColors.textMuted,
                          ),
                        ),
                        obscureText: true,
                        style: const TextStyle(fontSize: 13),
                      ),
                      const SizedBox(height: 20),
                      DondeDavidButton(
                        text: '🔐 INICIAR SESIÓN DE TRABAJO',
                        variant: ButtonVariant.primaryOrange,
                        isLoading: widget.auth.isLoading,
                        width: double.infinity,
                        onPressed: () => _attemptLogin(
                          _userController.text,
                          _passController.text,
                        ),
                      ),
                      if (_canUseBiometrics) ...[
                        const SizedBox(height: 12),
                        OutlinedButton.icon(
                          onPressed: _loginWithBiometrics,
                          icon: const Icon(
                            Icons.fingerprint,
                            color: AppColors.cyanAccent,
                            size: 22,
                          ),
                          label: const Text(
                            'Confirmar con biometría',
                            style: TextStyle(
                              color: AppColors.cyanAccent,
                              fontWeight: FontWeight.w800,
                              fontSize: 12,
                            ),
                          ),
                          style: OutlinedButton.styleFrom(
                            side: const BorderSide(color: AppColors.cyanAccent),
                            minimumSize: const Size.fromHeight(44),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),

                if (kDebugMode &&
                    const bool.fromEnvironment('ENABLE_DEMO_LOGINS')) ...[
                  const SizedBox(height: 20),
                  _buildDemoLoginCard(),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildQuickRoleBtn(String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white.withAlpha(12),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppColors.border),
        ),
        child: Center(
          child: Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w800,
              fontSize: 12,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDemoLoginCard() {
    return DondeDavidCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          const Text(
            'ACCESOS DIRECTOS DEMO:',
            style: TextStyle(
              color: AppColors.textMuted,
              fontSize: 11,
              fontWeight: FontWeight.w900,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 12),
          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 2,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
            childAspectRatio: 2.6,
            children: [
              _buildQuickRoleBtn(
                '⚙️ Admin',
                () => _attemptLogin('admin', 'admin123'),
              ),
              _buildQuickRoleBtn(
                '💰 Caja POS',
                () => _attemptLogin('caja', 'caja123'),
              ),
              _buildQuickRoleBtn(
                '👨‍🍳 Cocina KDS',
                () => _attemptLogin('cocina1', 'cocina123'),
              ),
              _buildQuickRoleBtn(
                '🛵 Repartidor',
                () => _attemptLogin('delivery1', 'delivery123'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
