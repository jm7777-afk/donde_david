import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';

class StatusBadge extends StatelessWidget {
  final String status;

  const StatusBadge({super.key, required this.status});

  @override
  Widget build(BuildContext context) {
    Color bg;
    Color fg;
    IconData icon;
    String label = status;

    switch (status.toUpperCase()) {
      case 'PENDIENTE':
      case 'EN_ESPERA':
        bg = AppColors.warning.withAlpha(40);
        fg = AppColors.warning;
        icon = Icons.hourglass_top;
        label = 'Pendiente';
        break;
      case 'COBRADO':
        bg = AppColors.brandBlue.withAlpha(40);
        fg = AppColors.brandBlue;
        icon = Icons.receipt_long;
        label = 'Cobrado';
        break;
      case 'EN_PREPARACION':
      case 'PREPARANDO':
        bg = AppColors.brandOrange.withAlpha(40);
        fg = AppColors.brandOrange;
        icon = Icons.soup_kitchen;
        label = 'En Preparación';
        break;
      case 'LISTO':
      case 'LISTO_PARA_RETIRAR':
        bg = AppColors.success.withAlpha(40);
        fg = AppColors.success;
        icon = Icons.check_circle;
        label = '¡Listo!';
        break;
      case 'ENTREGADO':
      case 'RETIRADO':
        bg = AppColors.success.withAlpha(40);
        fg = AppColors.success;
        icon = Icons.done_all;
        label = 'Entregado';
        break;
      case 'CANCELADO':
        bg = AppColors.danger.withAlpha(40);
        fg = AppColors.danger;
        icon = Icons.cancel;
        label = 'Cancelado';
        break;
      case 'PAGADO':
        bg = AppColors.success.withAlpha(40);
        fg = AppColors.success;
        icon = Icons.attach_money;
        label = 'Pagado';
        break;
      case 'PENDIENTE_VALIDACION':
      case 'PAGO_PENDIENTE':
        bg = AppColors.warning.withAlpha(40);
        fg = AppColors.warning;
        icon = Icons.pending;
        label = 'Validar Pago';
        break;
      case 'LIBRE':
        bg = AppColors.success.withAlpha(40);
        fg = AppColors.success;
        icon = Icons.event_seat;
        label = 'Libre';
        break;
      case 'OCUPADA':
        bg = AppColors.warning.withAlpha(40);
        fg = AppColors.warning;
        icon = Icons.people;
        label = 'Ocupada';
        break;
      case 'PENDIENTE_LIMPIEZA':
        bg = AppColors.danger.withAlpha(40);
        fg = AppColors.danger;
        icon = Icons.cleaning_services;
        label = 'Requiere Limpieza';
        break;
      case 'EN_LIMPIEZA':
        bg = AppColors.brandBlue.withAlpha(40);
        fg = AppColors.brandBlue;
        icon = Icons.sanitizer;
        label = 'En Limpieza';
        break;
      default:
        bg = AppColors.disabled.withAlpha(40);
        fg = AppColors.textSecondary;
        icon = Icons.info_outline;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: fg.withAlpha(120), width: 1),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, color: fg, size: 13),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
              color: fg,
              fontSize: 11,
              fontWeight: FontWeight.w800,
            ),
          ),
        ],
      ),
    );
  }
}
