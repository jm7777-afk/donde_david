import 'dart:async';
import 'package:flutter/material.dart';
import 'core/services/api_service.dart';
import 'core/services/notification_service.dart';
import 'core/services/offline_cache_service.dart';
import 'core/services/storage_service.dart';
import 'core/services/websocket_service.dart';
import 'core/theme/app_theme.dart';
import 'providers/auth_provider.dart';
import 'providers/cart_provider.dart';
import 'providers/catalog_provider.dart';
import 'providers/order_provider.dart';
import 'providers/staff_provider.dart';
import 'screens/welcome_gateway_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // 1. Inicializar servicios de persistencia, red y caché offline
  final storage = await StorageService.getInstance();
  final api = ApiService(storage);
  final ws = WebSocketService(storage);
  final cache = storage.prefs != null
      ? OfflineCacheService(storage.prefs!)
      : null;
  final notifications = NotificationService(ws);

  // 2. Inicializar proveedores de estado con soporte offline y tiempo real
  final authProvider = AuthProvider(api, storage, ws);
  final catalogProvider = CatalogProvider(api, storage, cache);
  final cartProvider = CartProvider();
  final orderProvider = OrderProvider(api);
  final staffProvider = StaffProvider(api, ws);

  runApp(
    DondeDavidApp(
      storage: storage,
      api: api,
      ws: ws,
      cache: cache,
      notifications: notifications,
      auth: authProvider,
      catalog: catalogProvider,
      cart: cartProvider,
      order: orderProvider,
      staff: staffProvider,
    ),
  );
}

class DondeDavidApp extends StatefulWidget {
  final StorageService storage;
  final ApiService api;
  final WebSocketService ws;
  final OfflineCacheService? cache;
  final NotificationService notifications;
  final AuthProvider auth;
  final CatalogProvider catalog;
  final CartProvider cart;
  final OrderProvider order;
  final StaffProvider staff;

  const DondeDavidApp({
    super.key,
    required this.storage,
    required this.api,
    required this.ws,
    this.cache,
    required this.notifications,
    required this.auth,
    required this.catalog,
    required this.cart,
    required this.order,
    required this.staff,
  });

  @override
  State<DondeDavidApp> createState() => _DondeDavidAppState();
}

class _DondeDavidAppState extends State<DondeDavidApp> {
  final GlobalKey<ScaffoldMessengerState> _scaffoldMessengerKey =
      GlobalKey<ScaffoldMessengerState>();
  StreamSubscription<InAppNotification>? _notifSubscription;

  @override
  void initState() {
    super.initState();
    // Escuchar cambios en los proveedores para reconstruir la app de forma reactiva
    widget.auth.addListener(_onStateChange);
    widget.catalog.addListener(_onStateChange);
    widget.cart.addListener(_onStateChange);
    widget.order.addListener(_onStateChange);
    widget.staff.addListener(_onStateChange);

    // Escuchar notificaciones push / WebSocket en vivo
    _notifSubscription = widget.notifications.notificationStream.listen((
      notif,
    ) {
      _scaffoldMessengerKey.currentState?.showSnackBar(
        SnackBar(
          backgroundColor: notif.color,
          duration: const Duration(seconds: 4),
          behavior: SnackBarBehavior.floating,
          content: Row(
            children: [
              Icon(notif.icon, color: Colors.black, size: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      notif.title,
                      style: const TextStyle(
                        color: Colors.black,
                        fontWeight: FontWeight.w900,
                        fontSize: 12,
                      ),
                    ),
                    Text(
                      notif.message,
                      style: const TextStyle(
                        color: Colors.black,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      );
    });
  }

  @override
  void dispose() {
    _notifSubscription?.cancel();
    widget.auth.removeListener(_onStateChange);
    widget.catalog.removeListener(_onStateChange);
    widget.cart.removeListener(_onStateChange);
    widget.order.removeListener(_onStateChange);
    widget.staff.removeListener(_onStateChange);
    super.dispose();
  }

  void _onStateChange() {
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      scaffoldMessengerKey: _scaffoldMessengerKey,
      title: 'DONDE DAVID Fast Food',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: WelcomeGatewayScreen(
        storage: widget.storage,
        catalog: widget.catalog,
        cart: widget.cart,
        auth: widget.auth,
        order: widget.order,
        staff: widget.staff,
      ),
    );
  }
}
