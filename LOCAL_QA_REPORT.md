# Reporte de QA técnico local — DONDE DAVID

## Alcance de la última verificación

La verificación local cubrió el backend, las migraciones, los flujos por rol y las pantallas estáticas. No equivale a una certificación de seguridad ni a una validación visual autenticada de todos los breakpoints.

| Verificación | Resultado |
|---|---|
| `pytest tests -v --tb=short` | 58 pruebas pasaron (0 fallos, 0 warnings) |
| `pytest backend/scripts/test_api.py -v --tb=short` | 9 pruebas pasaron (0 fallos) |
| `python -m compileall -q backend tests` | Correcto |
| `git diff --check` | Correcto |
| `alembic upgrade head` en SQLite desechable | Correcto (`f9c1d2e3a4b5`) |
| `alembic check` contra modelos ORM | Sin operaciones pendientes (`exit 0`) |
| Generación SQL de Alembic para PostgreSQL offline (`alembic upgrade head --sql`) | Correcta (`exit 0`; sin conexión directa a la BD en Render) |
| `node --check` sobre todos los JS de `backend/static/js/` | Correcto (`exit 0`) |
| Validación de entorno `ENVIRONMENT=production` | Rechaza `SECRET_KEY` débil y normaliza `postgres://` a `postgresql+psycopg://` |
| `/health` y `/ready` | Correcto; base de datos conectada |
| Casos de prueba | Matriz completa RBAC (9 perfiles), concurrencia/idempotencia de cobros y stock, OTP con `X-Order-Tracking-Token`, canje de puntos con bloqueo, validaciones admin, métricas filtrables por categoría/método, E2E QR → Cocina → Mesero → Caja → Limpieza, higiene frontend/seguridad y estilos HTML |

## Controles incorporados

- Producción exige una clave JWT aleatoria, PostgreSQL y orígenes CORS exactos.
- No se siembran datos de demostración en producción ni se permite invocar el seed allí.
- Admin/caja y WebSockets requieren autorización; pedidos de clientes se recalculan en backend.
- Login, registro, recuperación, OTP, pedidos públicos, reseñas y setup tienen límites por IP en memoria.
- Los cobros insuficientes no se aceptan; ventas, stock, turno y movimientos se confirman en una transacción.
- El stock se restaura y audita cuando se cancela un pedido no pagado.
- Los uploads validan extensión, MIME, firma y tamaño.
- Los errores internos se registran en servidor y se responden sin detalles sensibles.
- El perfil de usuario nuevo parte de historial y dirección vacíos; solo conserva los 50 puntos de bienvenida definidos explícitamente por el registro.
- El panel administrativo antiguo redirige al panel vigente para evitar presentar métricas estáticas de demostración, y el dashboard administrativo soporta filtrado real por categoría y método de pago.
- Las recomendaciones del cliente se calculan localmente con historial y ventas; no se envían datos a un proveedor de IA externo.
- Se eliminaron los accesos rápidos con credenciales demo en `login.html`, el guardado de contraseñas en `localStorage`, las referencias rotas de POS (`#view-btn-app-payments`, `#pos-history-payment-filter`) y las interpolaciones HTML sin escape en los paneles JS de operación y administración.
- Se desindexó `restaurante.db` del control de versiones Git conservando respaldo local fuera del índice.

## Pendientes antes de operación real

- Crear el PostgreSQL de producción, cargar secretos y configurar CORS en Render; esto no se puede comprobar desde el entorno local.
- Revisar y respaldar bases SQLite existentes antes de adoptarlas con Alembic. La migración inicial se diseñó para una base nueva.
- Configurar almacenamiento de objetos persistente para uploads en Render.
- Usar Redis o un broker compartido antes de escalar a múltiples procesos/instancias: el rate limiter y los eventos WebSocket se mantienen en memoria.
- Configurar un proveedor real de recuperación por correo/SMS; el endpoint permanece deshabilitado de forma explícita.
- Ejecutar pruebas visuales/manuales de UI por rol y dispositivo. No se declara aquí que los breakpoints se hayan vuelto a comprobar.
- La generación de QR todavía utiliza el servicio externo `api.qrserver.com`; configurar proxy/origen confiables en producción o alojar la generación internamente.
- No se seleccionó ni conectó una pasarela de pago en esta implementación.
- Probar en ambiente real la integración de tasa BCV y el flujo de delivery antes de operación.
- Añadir observabilidad operativa, política de respaldo/restauración y pruebas de concurrencia en PostgreSQL antes de abrir el sistema a datos reales.
