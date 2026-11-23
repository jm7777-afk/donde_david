import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'storage_service.dart';

class ApiException implements Exception {
  final String message;
  final int statusCode;

  ApiException(this.message, [this.statusCode = 0]);

  @override
  String toString() => message;
}

class ApiService {
  final StorageService _storage;

  ApiService(this._storage);

  String get _baseUrl => _storage.getBaseUrl();

  Map<String, String> _headers([bool requireAuth = false]) {
    final map = <String, String>{
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (requireAuth) {
      final token = _storage.getToken();
      if (token != null && token.isNotEmpty) {
        map['Authorization'] = 'Bearer $token';
      }
    }
    return map;
  }

  Uri _buildUri(String path, [Map<String, dynamic>? queryParams]) {
    final fullUrl = '$_baseUrl$path';
    final uri = Uri.parse(fullUrl);
    if (queryParams != null && queryParams.isNotEmpty) {
      final stringParams = queryParams.map((k, v) => MapEntry(k, v.toString()));
      return uri.replace(queryParameters: stringParams);
    }
    return uri;
  }

  dynamic _processResponse(http.Response response) {
    dynamic body;
    try {
      body = jsonDecode(utf8.decode(response.bodyBytes));
    } catch (_) {
      body = response.body;
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return body;
    }

    String errorMessage = 'Error ${response.statusCode}';
    if (body is Map) {
      if (body.containsKey('detail')) {
        final detail = body['detail'];
        if (detail is String) {
          errorMessage = detail;
        } else if (detail is List && detail.isNotEmpty) {
          errorMessage = detail.map((e) => e['msg'] ?? e.toString()).join(', ');
        }
      } else if (body.containsKey('message')) {
        errorMessage = body['message'].toString();
      }
    }

    throw ApiException(errorMessage, response.statusCode);
  }

  Future<dynamic> get(
    String path, {
    Map<String, dynamic>? queryParams,
    bool requireAuth = false,
    Duration timeout = const Duration(seconds: 15),
  }) async {
    try {
      final uri = _buildUri(path, queryParams);
      final response = await http
          .get(uri, headers: _headers(requireAuth))
          .timeout(timeout);
      return _processResponse(response);
    } on SocketException catch (_) {
      throw ApiException(
        'No se pudo conectar al servidor ($_baseUrl). Verifica que esté encendido y en la misma red.',
      );
    } on TimeoutException catch (_) {
      throw ApiException('Tiempo de espera agotado al conectar al servidor.');
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('Error inesperado de conexión: $e');
    }
  }

  Future<dynamic> post(
    String path, {
    dynamic body,
    bool requireAuth = false,
    Duration timeout = const Duration(seconds: 20),
  }) async {
    try {
      final uri = _buildUri(path);
      final response = await http
          .post(
            uri,
            headers: _headers(requireAuth),
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(timeout);
      return _processResponse(response);
    } on SocketException catch (_) {
      throw ApiException(
        'No se pudo conectar al servidor ($_baseUrl). Verifica tu conexión de red.',
      );
    } on TimeoutException catch (_) {
      throw ApiException('Tiempo de espera agotado al enviar la solicitud.');
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('Error al procesar solicitud: $e');
    }
  }

  Future<dynamic> put(
    String path, {
    dynamic body,
    Map<String, dynamic>? queryParams,
    bool requireAuth = false,
    Duration timeout = const Duration(seconds: 15),
  }) async {
    try {
      final uri = _buildUri(path, queryParams);
      final response = await http
          .put(
            uri,
            headers: _headers(requireAuth),
            body: body != null ? jsonEncode(body) : null,
          )
          .timeout(timeout);
      return _processResponse(response);
    } on SocketException catch (_) {
      throw ApiException('No se pudo conectar al servidor ($_baseUrl).');
    } on TimeoutException catch (_) {
      throw ApiException('Tiempo de espera agotado.');
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('Error al actualizar: $e');
    }
  }

  Future<dynamic> delete(
    String path, {
    bool requireAuth = false,
    Duration timeout = const Duration(seconds: 15),
  }) async {
    try {
      final uri = _buildUri(path);
      final response = await http
          .delete(uri, headers: _headers(requireAuth))
          .timeout(timeout);
      return _processResponse(response);
    } on SocketException catch (_) {
      throw ApiException('No se pudo conectar al servidor.');
    } on TimeoutException catch (_) {
      throw ApiException('Tiempo de espera agotado.');
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('Error al eliminar: $e');
    }
  }
}
