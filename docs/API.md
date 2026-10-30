# Referencia práctica de la API

La API usa el prefijo `/api/v1`. La especificación OpenAPI generada por la aplicación es la referencia completa de rutas y modelos en `/docs` y `/openapi.json` una vez habilitado el sistema.

## Autenticación

`POST /api/v1/auth/login`

```json
{
  "nombre_usuario": "usuario",
  "password": "contraseña"
}
```

Devuelve `access_token`, `token_type` y el perfil del usuario. Envía el token en operaciones protegidas:

```http
Authorization: Bearer <access_token>
```

El registro requiere contraseñas de al menos 12 caracteres. Límites actuales por IP: login 10/minuto, registro 5/hora, recuperación 3/hora. La recuperación devuelve `501` hasta configurar un proveedor real de correo o SMS; no informa falsamente que el mensaje fue enviado.

## Cliente y pedidos QR

- Catálogo público: `GET /api/v1/cliente/categorias`, `GET /api/v1/cliente/productos`
- Datos públicos: `GET /api/v1/cliente/configuraciones-publicas`, `/publicaciones`, `/promociones`, `/resenas` y `/guia`
- Crear pedido: `POST /api/v1/cliente/pedidos`
- Historial y puntos: requieren sesión de cliente.

Ejemplo de pedido:

```json
{
  "numero_mesa": "Mesa 5",
  "tipo": "mesa",
  "detalles": [
    {
      "producto_id": 1,
      "cantidad": 2,
      "personalizaciones": {"sin_cebolla": true}
    }
  ]
}
```

El servidor determina precios, impuestos, cargos y stock; nunca confía en importes calculados por el navegador. La cantidad por producto debe ser positiva y no superar 100. Creación de pedidos: 20/hora/IP. Para cambiar de mesa, el pedido debe pertenecer al usuario autenticado; pedidos de invitado no pueden modificarse después de crearse.

- Los productos admiten `extras_json` como una lista JSON de opciones `{ "nombre": "...", "precio": 1.25 }` y `media_json` como una lista de recursos `{ "tipo": "imagen|video", "url": "https://..." }`. Administración valida estructura, nombres, precios, duplicados y URLs. El cliente envía `personalizaciones.extras` con los nombres elegidos; el servidor acepta solo opciones activas configuradas y calcula su precio antes de crear el pedido. No envíes precios desde el navegador.
- En pedidos `tipo=delivery`, `delivery_lat` y `delivery_lng` son opcionales, pero deben enviarse juntos y dentro de los rangos geográficos válidos. Se devuelven en el pedido para uso operativo del repartidor. En las modalidades `mesa` y `llevar` no se aceptan coordenadas.
- `google_maps_api_key` se configura desde Administración y se incluye en la configuración pública para cargar el mapa en el navegador. Es una clave pública: restríngela en Google Cloud a los dominios autorizados y habilita únicamente las APIs necesarias. El cliente conserva un mapa OpenStreetMap como alternativa si no hay clave.

- `GET /api/v1/cliente/personalizacion`: requiere sesión. Devuelve saludo, puntos, última orden utilizable y hasta tres recomendaciones basadas en coocurrencia del historial y ventas pagadas reales. Solo recomienda productos activos, disponibles y con stock; no envía datos a servicios de IA externos ni inventa pedidos para usuarios nuevos.
- `POST /api/v1/cliente/solicitudes-mesa`: petición desde un QR con `numero_mesa`, `tipo` (`LLAMAR_MESERO` o `SOLICITAR_CUENTA`) y, opcionalmente, `pedido_id`/`nota`. Está limitada a 6 solicitudes por minuto y evita crear duplicados pendientes por mesa y tipo.
- Los pedidos `tipo=llevar` reciben un código aleatorio de retiro de seis dígitos en la respuesta de creación. El código no se incluye en listas de caja o cocina.

La verificación OTP (`POST /api/v1/cliente/pedidos/verificar-otp`) está limitada a 10/minuto/IP. No existe un código maestro de prueba.

### Cobros, moneda y tasa

`GET /api/v1/cliente/configuraciones-publicas` devuelve la tasa almacenada, su fuente, fecha y estado. La actualización automática usa el feed de DolarApi configurado en `BCV_RATE_API_URL`, que publica una referencia de fuente oficial; no es una API operada directamente por el BCV. Si el proveedor no responde, se conserva la última tasa válida. Una tasa manual guardada desde Administración prevalece hasta que un administrador pulse la actualización del feed.

- Pago Móvil requiere moneda VES, una referencia completa y datos bancarios configurados. El pedido queda `PAGO_PENDIENTE` / `PENDIENTE_VALIDACION` y no se libera a cocina hasta validación manual en caja.
- Efectivo y punto de venta físico quedan pendientes de cobro en caja. El endpoint `POST /api/v1/caja/pedidos/{id}/cobrar` valida el importe en USD o VES con la tasa disponible y guarda la moneda, importe y tasa aplicada.
- Una cuenta abierta de mesa (`modo_pago=PAGAR_DESPUES`) se crea sin método ni importe pagado; caja registra el pago al cerrar la cuenta.
- Rechazar un Pago Móvil cancela el pedido, repone el inventario con movimientos de auditoría y libera la mesa si no tiene otros pedidos abiertos.

## Caja, cocina y administración

- Caja (`/api/v1/caja`): roles admin, supervisor o caja. Incluye turnos, pedidos pendientes/cobrados, cobro, facturas y búsqueda de clientes. `GET /turno-activo` informa efectivo esperado y esperado por medio. `POST /movimientos` registra egresos por turno, concepto y medio; `GET /movimientos` permite auditarlos mientras el turno está abierto. `POST /cerrar-turno` acepta `arqueo` con exactamente `Efectivo`, `Pago Móvil` y `Punto de Venta`, en USD equivalente. El efectivo esperado suma apertura y cobros en efectivo y resta egresos de efectivo; cada medio digital también descuenta sus egresos. `GET /productos-frecuentes` resume productos pagados de los últimos 30 días. Cobros insuficientes se rechazan y no alteran el pedido.
- Cocina (`/api/v1/cocina`): roles admin, supervisor, caja, cocina o mesero. `GET /pedidos?tipo=mesa|llevar|delivery` filtra la modalidad; sin `tipo` conserva el listado completo. Al cancelar pedidos no cobrados se restaura stock y se registra el movimiento; pedidos pagados no pueden cancelarse desde este flujo.
- Mesero (`/api/v1/mesero`): operaciones del salón protegidas por rol. `GET /mesas` incluye antigüedad en minutos y cantidad de pedidos activos calculadas desde los pedidos abiertos.
- Solicitudes del salón: `GET /api/v1/mesero/solicitudes` lista solicitudes pendientes; `PUT /api/v1/mesero/solicitudes/{id}/estado` acepta `ATENDIDA` o `CANCELADA`. Los eventos `SOLICITUD_MESA` y `SOLICITUD_MESA_ACTUALIZADA` notifican a las pantallas conectadas.
- Administración (`/api/v1/admin`): todas las rutas requieren admin o supervisor. Asignar o crear el rol admin está reservado a admin.
- Delivery (`/api/v1/delivery`): caja/admin/supervisor consultan pedidos y repartidores y asignan solo pedidos pagados. El repartidor autenticado actualiza su propio pedido de `ASIGNADO` a `RECOGIDO`, `EN_CAMINO` y `ENTREGADO`; la entrega requiere OTP. El OTP no se expone en las respuestas del repartidor.
- Gerencia (`/api/v1/gerencia/dashboard`): solo rol `gerente`; entrega indicadores agregados de ventas pagadas, cocina, mesas, delivery e inventario, sin información personal ni permisos administrativos.
- Productos: administración configura `disponible`, `alergenos` (declaración informativa) y `tiempo_preparacion` (1–240 minutos). El catálogo y la API de pedidos rechazan productos no disponibles o sin stock. La estimación de preparación no representa una ETA de traslado.
- Turnos: el backend registra `fecha_pago` cuando caja confirma o registra un cobro. Para datos anteriores a la migración se usa la fecha de creación como referencia aproximada en reportes.
- Retiro en mostrador: cocina cambia el pedido `llevar` a `LISTO_PARA_RETIRAR`; `GET /api/v1/caja/pedidos-retiro` lo muestra sin exponer el código. Caja lo entrega mediante `POST /api/v1/caja/pedidos/{id}/confirmar-retiro` con `codigo_retiro`; una coincidencia constante del código marca el pedido como `RETIRADO` y `ENTREGADO`. El OTP de delivery sigue siendo independiente.
- QR: `GET /api/v1/admin/mesas/{numero_mesa}/qr` forma el enlace desde el host de la solicitud actual y codifica el destino para el servicio de imagen QR. En producción, el proxy debe enviar `Host` y `X-Forwarded-Proto` confiables.
- Datos iniciales: el seed de desarrollo crea mesas libres y no abre turnos ni genera pedidos/ventas ficticios. El dashboard muestra cero y porcentajes cero si todavía no existen cobros.
- Auditoría: `GET /api/v1/admin/inventario/movimientos` permite consultar movimientos de inventario, con `limit` (1–500) y `offset`.
- Uploads: `POST /api/v1/admin/upload`, imágenes JPEG/PNG/WEBP válidas, máximo 5 MB.

## Instalación y diagnóstico

- `GET /api/v1/setup/status` consulta si se completó la instalación.
- `POST /api/v1/setup/install` crea la primera cuenta admin y se bloquea al completar el proceso. Contraseña mínima de 12 caracteres.
- `GET /health` comprueba el proceso; `GET /ready` comprueba la base de datos y responde 503 si no está disponible.

## WebSocket

Conecta a `/ws` usando `ws://` en local o `wss://` en HTTPS. En el primer mensaje, envía:

```json
{"token": "<access_token>"}
```

Solo cuentas activas de personal pueden conectarse. El servidor cierra conexiones sin token, con token inválido o de rol cliente antes de incorporarlas al canal de eventos.
