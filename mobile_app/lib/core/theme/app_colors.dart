import 'package:flutter/material.dart';

/// Design tokens and semantic color palette matching `DESIGN_SYSTEM.md`
class AppColors {
  // Brand Palette
  static const Color brandNavy = Color(
    0xFF071A3D,
  ); // Estructura, headers, modo oscuro
  static const Color brandNavyDark = Color(
    0xFF0B2557,
  ); // Superficie secundaria navy
  static const Color brandBlue = Color(
    0xFF0879E8,
  ); // Enlaces, estados activos, tecnología
  static const Color brandBlueLight = Color(0xFFEAF4FF); // Fondos suaves
  static const Color brandOrange = Color(
    0xFFFF7A00,
  ); // CTAs primarios, precios, acción
  static const Color brandOrangeDark = Color(
    0xFFD95F00,
  ); // Pressed/Hover de CTAs
  static const Color brandYellow = Color(
    0xFFFFC400,
  ); // Promos, "BOOM!", estrellas
  static const Color goldAccent = Color(
    0xFFFFBC0D,
  ); // Acento dorado estilo McDonald's / Fast Food
  static const Color cyanAccent = Color(
    0xFF00F5D4,
  ); // Acento cian para QR, 1-Clic y Delivery
  static const Color electricTeal = Color(
    0xFF00F5D4,
  ); // Alias de cyanAccent (Teal eléctrico)
  static const Color navyLight = Color(0xFF0B2557); // Alias de brandNavyDark
  static const Color navyDark = Color(0xFF071A3D); // Alias de brandNavy

  // Semantic Feedback
  static const Color success = Color(0xFF22C55E); // Pedido listo, pagado, libre
  static const Color danger = Color(
    0xFFF21D1D,
  ); // Urgencia >15 min, error, cancelado
  static const Color warning = Color(
    0xFFF59E0B,
  ); // En cola, atención requerida, ocupado
  static const Color info = Color(0xFF38BDF8); // Notificaciones informativas

  // Theme Surfaces (Dark Theme Default)
  static const Color bgMain = Color(0xFF0B111E);
  static const Color bgSurface = Color(0xFF111827);
  static const Color bgCard = Color(0xD9111827); // rgba(17, 24, 39, 0.85)
  static const Color colorDark = Color(0xFF111318);
  static const Color border = Color(0xFF1E293B);
  static const Color disabled = Color(0xFF334155);

  // Typography
  static const Color textPrimary = Color(0xFFF8FAFC);
  static const Color textSecondary = Color(0xFF94A3B8);
  static const Color textMuted = Color(0xFF64748B);

  // Gradients
  static const LinearGradient goldGradient = LinearGradient(
    colors: [Color(0xFFFFC400), Color(0xFFFF7A00)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient cyanGradient = LinearGradient(
    colors: [Color(0xFF00F5D4), Color(0xFF00B4D8)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient navyGradient = LinearGradient(
    colors: [Color(0xFF071A3D), Color(0xFF0B111E)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );
}
