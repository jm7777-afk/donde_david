import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'storage_service.dart';

class WebSocketEvent {
  final String type;
  final dynamic data;

  WebSocketEvent({required this.type, required this.data});

  factory WebSocketEvent.fromJson(Map<String, dynamic> json) {
    return WebSocketEvent(
      type: json['event'] ?? json['type'] ?? 'UNKNOWN',
      data: json['data'] ?? json['payload'] ?? json,
    );
  }
}

class WebSocketService {
  final StorageService _storage;
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;
  bool _isConnected = false;
  bool _disposed = false;

  final StreamController<WebSocketEvent> _eventController =
      StreamController<WebSocketEvent>.broadcast();
  Stream<WebSocketEvent> get eventStream => _eventController.stream;

  bool get isConnected => _isConnected;

  WebSocketService(this._storage);

  void connect() {
    if (_disposed) return;
    final token = _storage.getToken();
    if (token == null || token.isEmpty) {
      if (kDebugMode) {
        print('[WS] No hay token de sesión para conectar al WebSocket.');
      }
      return;
    }

    final rawBaseUrl = _storage.getBaseUrl();
    final wsUrl =
        rawBaseUrl
            .replaceFirst('http://', 'ws://')
            .replaceFirst('https://', 'wss://') +
        '/ws';

    try {
      if (kDebugMode) {
        print('[WS] Conectando a $wsUrl ...');
      }
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));

      // Enviar primer handshake con token de autenticación
      _channel?.sink.add(jsonEncode({'token': token}));

      _subscription = _channel?.stream.listen(
        (data) {
          _isConnected = true;
          try {
            final parsed = jsonDecode(data.toString());
            if (parsed is Map<String, dynamic>) {
              _eventController.add(WebSocketEvent.fromJson(parsed));
            }
          } catch (e) {
            if (kDebugMode) {
              print('[WS] Mensaje no parseable: $data');
            }
          }
        },
        onError: (error) {
          if (kDebugMode) {
            print('[WS] Error: $error');
          }
          _handleDisconnect();
        },
        onDone: () {
          if (kDebugMode) {
            print('[WS] Conexión cerrada');
          }
          _handleDisconnect();
        },
      );
    } catch (e) {
      if (kDebugMode) {
        print('[WS] Fallo al abrir socket: $e');
      }
      _handleDisconnect();
    }
  }

  void _handleDisconnect() {
    _isConnected = false;
    _subscription?.cancel();
    _subscription = null;
    _channel = null;

    if (!_disposed) {
      _reconnectTimer?.cancel();
      _reconnectTimer = Timer(const Duration(seconds: 5), () {
        if (!_disposed) connect();
      });
    }
  }

  void disconnect() {
    _reconnectTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    _channel = null;
    _isConnected = false;
  }

  void dispose() {
    _disposed = true;
    disconnect();
    _eventController.close();
  }
}
