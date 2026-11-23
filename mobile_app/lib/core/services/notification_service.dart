import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../theme/app_colors.dart';
import 'websocket_service.dart';

class InAppNotification {
  final String title;
  final String message;
  final Color color;
  final IconData icon;
  final DateTime timestamp;

  InAppNotification({
    required this.title,
    required this.message,
    this.color = AppColors.goldAccent,
    this.icon = Icons.notifications,
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
}

class NotificationService {
  final WebSocketService _ws;
  StreamSubscription<WebSocketEvent>? _subscription;
  final StreamController<InAppNotification> _notificationsController =
      StreamController<InAppNotification>.broadcast();

  Stream<InAppNotification> get notificationStream =>
      _notificationsController.stream;

  NotificationService(this._ws) {
    _listenToEvents();
  }

  void _listenToEvents() {
    _subscription = _ws.eventStream.listen((event) {
      _processEvent(event);
    });
  }

  void _processEvent(WebSocketEvent event) {
    String title = 'DONDE DAVID';
    String message = 'Actualización en tiempo real';
    Color color = AppColors.goldAccent;
    IconData icon = Icons.notifications;

    final type = event.type.toUpperCase();
    final data = event.data is Map ? event.data as Map : {};

    switch (type) {
      case 'NUEVO_PEDIDO':
        title = '🔔 NUEVO PEDIDO RECIBIDO';
        message =
            'Pedido #${data["pedido_id"] ?? ""} (${data["tipo"] ?? "Salón"}) entró a cocina.';
        color = AppColors.brandOrange;
        icon = Icons.soup_kitchen;
        break;

      case 'PEDIDO_ACTUALIZADO':
        final estado = data['estado'] ?? data['estado_pago'] ?? 'ACTUALIZADO';
        title = '⚡ PEDIDO #${data["pedido_id"] ?? ""} $estado';
        message = 'El estado de la orden cambió a: $estado.';
        color = estado == 'LISTO' ? AppColors.success : AppColors.cyanAccent;
        icon = estado == 'LISTO' ? Icons.check_circle : Icons.sync;
        break;

      case 'SOLICITUD_MESA':
        final mesa = data['numero_mesa'] ?? 'Mesa';
        final solTipo = data['tipo'] ?? 'ATENCIÓN';
        title = '🙋 LLAMADA DEL SALÓN';
        message = '$mesa solicita: $solTipo';
        color = AppColors.warning;
        icon = Icons.room_service;
        break;

      case 'MESA_ACTUALIZADA':
        title = '🍽️ ESTADO DE MESA';
        message =
            'Mesa #${data["numero_mesa"] ?? ""} ahora está: ${data["estado"] ?? ""}';
        color = AppColors.brandBlue;
        icon = Icons.table_restaurant;
        break;

      default:
        title = 'ℹ️ NOTIFICACIÓN';
        message = 'Evento: ${event.type}';
        color = AppColors.textPrimary;
        icon = Icons.info_outline;
    }

    // Trigger haptic vibration feedback
    try {
      HapticFeedback.mediumImpact();
    } catch (_) {}

    final notif = InAppNotification(
      title: title,
      message: message,
      color: color,
      icon: icon,
    );

    _notificationsController.add(notif);
  }

  void dispose() {
    _subscription?.cancel();
    _notificationsController.close();
  }
}
