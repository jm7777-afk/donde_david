import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/donde_david_button.dart';
import '../../widgets/donde_david_card.dart';

class ProfileTab extends StatefulWidget {
  final AuthProvider auth;

  const ProfileTab({super.key, required this.auth});

  @override
  State<ProfileTab> createState() => _ProfileTabState();
}

class _ProfileTabState extends State<ProfileTab> {
  // Login Controllers
  final TextEditingController _loginUserCtrl = TextEditingController();
  final TextEditingController _loginPassCtrl = TextEditingController();

  // Register Controllers
  final TextEditingController _regNombreCtrl = TextEditingController();
  final TextEditingController _regApellidoCtrl = TextEditingController();
  final TextEditingController _regEmailCtrl = TextEditingController();
  final TextEditingController _regTelCtrl = TextEditingController();
  final TextEditingController _regUserCtrl = TextEditingController();
  final TextEditingController _regPassCtrl = TextEditingController();

  @override
  void dispose() {
    _loginUserCtrl.dispose();
    _loginPassCtrl.dispose();
    _regNombreCtrl.dispose();
    _regApellidoCtrl.dispose();
    _regEmailCtrl.dispose();
    _regTelCtrl.dispose();
    _regUserCtrl.dispose();
    _regPassCtrl.dispose();
    super.dispose();
  }

  void _openLoginModal() {
    showDialog(
      context: context,
      builder: (_) => StatefulBuilder(
        builder: (ctx, setModalState) => Dialog(
          insetPadding: const EdgeInsets.all(16),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  const Text('🔑', style: TextStyle(fontSize: 32)),
                  const SizedBox(height: 6),
                  const Text(
                    'INICIAR SESIÓN CLIENTE',
                    style: TextStyle(
                      color: AppColors.goldAccent,
                      fontWeight: FontWeight.w900,
                      fontSize: 16,
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Ingresa a tu cuenta para acumular puntos y repetir tus pedidos.',
                    style: TextStyle(color: AppColors.textMuted, fontSize: 11),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _loginUserCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Usuario o Correo',
                    ),
                    style: const TextStyle(fontSize: 13),
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: _loginPassCtrl,
                    decoration: const InputDecoration(labelText: 'Contraseña'),
                    obscureText: true,
                    style: const TextStyle(fontSize: 13),
                  ),
                  const SizedBox(height: 20),
                  DondeDavidButton(
                    text: 'INICIAR SESIÓN',
                    variant: ButtonVariant.gold,
                    isLoading: widget.auth.isLoading,
                    width: double.infinity,
                    onPressed: () async {
                      final ok = await widget.auth.login(
                        _loginUserCtrl.text,
                        _loginPassCtrl.text,
                      );
                      if (ok && mounted) {
                        Navigator.pop(ctx);
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                              '¡Bienvenido de nuevo ${widget.auth.user?.nombre}!',
                            ),
                          ),
                        );
                      } else if (mounted && widget.auth.errorMessage != null) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(widget.auth.errorMessage!),
                            backgroundColor: AppColors.danger,
                          ),
                        );
                      }
                    },
                  ),
                  const SizedBox(height: 12),
                  TextButton(
                    onPressed: () {
                      Navigator.pop(ctx);
                      _openRegisterModal();
                    },
                    child: const Text(
                      '¿No tienes cuenta? Regístrate (+50 Pts 🎁)',
                      style: TextStyle(
                        color: AppColors.cyanAccent,
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _openRegisterModal() {
    showDialog(
      context: context,
      builder: (_) => StatefulBuilder(
        builder: (ctx, setModalState) => Dialog(
          insetPadding: const EdgeInsets.all(16),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  const Text('🎁', style: TextStyle(fontSize: 32)),
                  const SizedBox(height: 6),
                  const Text(
                    'REGISTRO DE CLIENTE (+50 PTS)',
                    style: TextStyle(
                      color: AppColors.goldAccent,
                      fontWeight: FontWeight.w900,
                      fontSize: 15,
                    ),
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Regístrate para ganar un bono de 50 puntos de bienvenida.',
                    style: TextStyle(color: AppColors.textMuted, fontSize: 11),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _regNombreCtrl,
                          decoration: const InputDecoration(
                            labelText: 'Nombre',
                          ),
                          style: const TextStyle(fontSize: 12),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: TextField(
                          controller: _regApellidoCtrl,
                          decoration: const InputDecoration(
                            labelText: 'Apellido',
                          ),
                          style: const TextStyle(fontSize: 12),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _regEmailCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Correo Electrónico',
                    ),
                    keyboardType: TextInputType.emailAddress,
                    style: const TextStyle(fontSize: 12),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _regTelCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Teléfono Contacto',
                    ),
                    keyboardType: TextInputType.phone,
                    style: const TextStyle(fontSize: 12),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _regUserCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Nombre de Usuario',
                    ),
                    style: const TextStyle(fontSize: 12),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _regPassCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Contraseña (mín 12 caracteres)',
                    ),
                    obscureText: true,
                    style: const TextStyle(fontSize: 12),
                  ),
                  const SizedBox(height: 20),
                  DondeDavidButton(
                    text: 'REGISTRARME Y GANAR PUNTOS',
                    variant: ButtonVariant.gold,
                    isLoading: widget.auth.isLoading,
                    width: double.infinity,
                    onPressed: () async {
                      if (_regPassCtrl.text.length < 12) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              'La contraseña debe tener al menos 12 caracteres.',
                            ),
                          ),
                        );
                        return;
                      }
                      final ok = await widget.auth.register(
                        nombre: _regNombreCtrl.text,
                        apellido: _regApellidoCtrl.text,
                        email: _regEmailCtrl.text,
                        telefono: _regTelCtrl.text,
                        username: _regUserCtrl.text,
                        password: _regPassCtrl.text,
                      );
                      if (ok && mounted) {
                        Navigator.pop(ctx);
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              '¡Registro exitoso! Ganaste 50 puntos 🏆',
                            ),
                          ),
                        );
                      } else if (mounted && widget.auth.errorMessage != null) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(widget.auth.errorMessage!),
                            backgroundColor: AppColors.danger,
                          ),
                        );
                      }
                    },
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = widget.auth.user;
    final isAuth = widget.auth.isAuthenticated;

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 90),
      children: [
        // User Profile Card
        DondeDavidCard(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(
                  gradient: AppColors.goldGradient,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.goldAccent.withAlpha(100),
                      blurRadius: 16,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: const Center(
                  child: Text('👤', style: TextStyle(fontSize: 34)),
                ),
              ),
              const SizedBox(height: 12),
              Text(
                isAuth
                    ? user?.nombreCompleto ?? 'Cliente Donde David'
                    : 'Cliente Invitado',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                  fontSize: 18,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                isAuth
                    ? user?.email ?? user?.nombreUsuario ?? ''
                    : 'Navegando en modo pedido flash',
                style: const TextStyle(
                  color: AppColors.textMuted,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 14),

        // Loyalty Points Card
        DondeDavidCard(
          padding: const EdgeInsets.all(18),
          borderColor: AppColors.goldAccent,
          gradient: const LinearGradient(
            colors: [Color(0x33FFC400), Color(0x1800F5D4)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          child: Column(
            children: [
              const Text(
                'MIS PUNTOS DE FIDELIDAD',
                style: TextStyle(
                  color: AppColors.goldAccent,
                  fontWeight: FontWeight.w900,
                  fontSize: 11,
                  letterSpacing: 0.8,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '${isAuth ? user?.puntosFidelidad ?? 0 : 0} PUNTOS 🏆',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w900,
                  fontSize: 26,
                  letterSpacing: 0.5,
                ),
              ),
              const SizedBox(height: 4),
              const Text(
                'Los puntos se acreditan al confirmar el pago en caja y son canjeables por productos gratis.',
                style: TextStyle(
                  color: AppColors.cyanAccent,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),

        const SizedBox(height: 16),

        // Auth Actions or Logout
        if (!isAuth) ...[
          DondeDavidButton(
            text: '🔑 INICIAR SESIÓN EN MI CUENTA',
            variant: ButtonVariant.gold,
            width: double.infinity,
            onPressed: _openLoginModal,
          ),
          const SizedBox(height: 10),
          DondeDavidButton(
            text: '📝 REGISTRARME (+50 PUNTOS GRATIS)',
            variant: ButtonVariant.primaryOrange,
            width: double.infinity,
            onPressed: _openRegisterModal,
          ),
        ] else ...[
          DondeDavidButton(
            text: '🚪 CERRAR SESIÓN',
            variant: ButtonVariant.outline,
            width: double.infinity,
            onPressed: () async {
              await widget.auth.logout();
              if (mounted) {
                ScaffoldMessenger.of(
                  context,
                ).showSnackBar(const SnackBar(content: Text('Sesión cerrada')));
              }
            },
          ),
        ],

        const SizedBox(height: 24),

        // App Information & Version
        Center(
          child: Column(
            children: [
              Text(
                'DONDE DAVID Fast Food v1.0 Enterprise',
                style: TextStyle(
                  color: AppColors.textMuted.withAlpha(150),
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                'Diseño oficial Dark Neon & APIs REST + WebSocket',
                style: TextStyle(
                  color: AppColors.textMuted.withAlpha(100),
                  fontSize: 10,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
