import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';

class BrandHeader extends StatelessWidget implements PreferredSizeWidget {
  final String? activeTable;
  final double tasaCambioBs;
  final VoidCallback? onTableTap;
  final VoidCallback? onSettingsTap;
  final VoidCallback? onStaffPortalTap;

  const BrandHeader({
    super.key,
    this.activeTable,
    required this.tasaCambioBs,
    this.onTableTap,
    this.onSettingsTap,
    this.onStaffPortalTap,
  });

  @override
  Size get preferredSize => const Size.fromHeight(68);

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + 8,
        bottom: 8,
        left: 16,
        right: 16,
      ),
      decoration: BoxDecoration(
        color: const Color(0xFF101726).withAlpha(245),
        border: const Border(
          bottom: BorderSide(color: AppColors.border, width: 1),
        ),
      ),
      child: Row(
        children: [
          if (Navigator.canPop(context)) ...[
            IconButton(
              icon: const Icon(
                Icons.arrow_back_ios,
                color: AppColors.goldAccent,
                size: 16,
              ),
              tooltip: 'Volver a Pantalla Principal',
              onPressed: () => Navigator.pop(context),
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(),
            ),
            const SizedBox(width: 8),
          ],

          // Brand Logo
          ClipRRect(
            borderRadius: BorderRadius.circular(20),
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                border: Border.all(color: AppColors.goldAccent, width: 1.5),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Image.asset(
                'assets/images/logo-donde-david.jpg',
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => const Icon(
                  Icons.fastfood,
                  color: AppColors.goldAccent,
                  size: 22,
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),

          // Title & Subtitle
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                const Row(
                  children: [
                    Text(
                      'DONDE DAVID',
                      style: TextStyle(
                        color: AppColors.goldAccent,
                        fontSize: 15,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.8,
                      ),
                    ),
                    SizedBox(width: 4),
                    Text('🍔', style: TextStyle(fontSize: 14)),
                  ],
                ),
                Text(
                  activeTable != null
                      ? 'Ubicado en: $activeTable'
                      : 'Fresh & Tasty! Fast Food',
                  style: TextStyle(
                    color: activeTable != null
                        ? AppColors.cyanAccent
                        : AppColors.textMuted,
                    fontSize: 11,
                    fontWeight: activeTable != null
                        ? FontWeight.w800
                        : FontWeight.w600,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),

          // Active Table / QR Indicator Button
          if (activeTable != null)
            InkWell(
              onTap: onTableTap,
              borderRadius: BorderRadius.circular(16),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 5,
                ),
                decoration: BoxDecoration(
                  gradient: AppColors.cyanGradient,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: AppColors.cyanAccent.withAlpha(70),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.qr_code, color: Colors.black, size: 14),
                    const SizedBox(width: 4),
                    Text(
                      activeTable!,
                      style: const TextStyle(
                        color: Colors.black,
                        fontWeight: FontWeight.w900,
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ),

          if (activeTable != null) const SizedBox(width: 8),

          // Settings (Server IP / Config)
          IconButton(
            onPressed: onSettingsTap,
            icon: const Icon(
              Icons.tune,
              color: AppColors.textSecondary,
              size: 20,
            ),
            tooltip: 'Configuración Servidor',
            visualDensity: VisualDensity.compact,
          ),

          // Staff Portal Switcher
          IconButton(
            onPressed: onStaffPortalTap,
            icon: const Icon(
              Icons.badge,
              color: AppColors.goldAccent,
              size: 20,
            ),
            tooltip: 'Portal de Personal',
            visualDensity: VisualDensity.compact,
          ),
        ],
      ),
    );
  }
}
