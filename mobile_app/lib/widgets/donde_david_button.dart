import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';

enum ButtonVariant { primaryOrange, gold, secondaryBlue, outline, danger }

class DondeDavidButton extends StatelessWidget {
  final String text;
  final VoidCallback? onPressed;
  final ButtonVariant variant;
  final Widget? icon;
  final bool isLoading;
  final double? width;
  final double height;

  const DondeDavidButton({
    super.key,
    required this.text,
    required this.onPressed,
    this.variant = ButtonVariant.primaryOrange,
    this.icon,
    this.isLoading = false,
    this.width,
    this.height = 48,
  });

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return SizedBox(
        width: width,
        height: height,
        child: const Center(
          child: CircularProgressIndicator(
            strokeWidth: 2.5,
            valueColor: AlwaysStoppedAnimation<Color>(AppColors.goldAccent),
          ),
        ),
      );
    }

    BoxDecoration decoration;
    Color textColor = Colors.white;

    switch (variant) {
      case ButtonVariant.primaryOrange:
        decoration = BoxDecoration(
          color: AppColors.brandOrange,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: AppColors.brandOrange.withAlpha(90),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        );
        break;
      case ButtonVariant.gold:
        decoration = BoxDecoration(
          gradient: AppColors.goldGradient,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: AppColors.goldAccent.withAlpha(100),
              blurRadius: 14,
              offset: const Offset(0, 4),
            ),
          ],
        );
        textColor = Colors.black;
        break;
      case ButtonVariant.secondaryBlue:
        decoration = BoxDecoration(
          color: AppColors.brandBlue,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(
              color: AppColors.brandBlue.withAlpha(80),
              blurRadius: 10,
              offset: const Offset(0, 3),
            ),
          ],
        );
        break;
      case ButtonVariant.danger:
        decoration = BoxDecoration(
          color: AppColors.danger,
          borderRadius: BorderRadius.circular(12),
        );
        break;
      case ButtonVariant.outline:
        decoration = BoxDecoration(
          color: Colors.transparent,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border, width: 1.5),
        );
        textColor = AppColors.textPrimary;
        break;
    }

    return Container(
      width: width,
      height: height,
      decoration: decoration,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(12),
          child: Center(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (icon != null) ...[icon!, const SizedBox(width: 8)],
                Text(
                  text,
                  style: TextStyle(
                    color: textColor,
                    fontWeight: FontWeight.w800,
                    fontSize: 14,
                    letterSpacing: 0.3,
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
