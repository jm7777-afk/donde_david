# Reporte de QA técnico local — DONDE DAVID

## Alcance de la última verificación

La verificación local cubrió el backend, las migraciones, los flujos por rol y las pantallas estáticas. No equivale a una certificación de seguridad ni a una validación visual autenticada de todos los breakpoints.

| Verificación | Resultado |
|---|---|
| `pytest -q` | 44 pruebas pasaron |
| `python -m compileall -q backend tests` | Correcto |
| `git diff --check` | Correcto |
| `alembic upgrade head` en SQLite desechable | Correcto |
| `alembic check` contra modelos ORM | Sin operaciones pendientes |
| Generación SQL de Alembic para PostgreSQL offline | Correcta; no conectó a una base real |
| `node --check` en los scripts principales | Correcto |
| Escaneo HTML | 12 páginas; sin IDs duplicados ni recursos estáticos locales ausentes |
| `/health` y `/ready` | Correcto; base de datos conectada |
| Casos de prueba | RBAC, credenciales, validación de importes, autenticación WebSocket, cancelación/reposición de stock, auditoría, solicitudes QR, personalización, retiro, arqueo de caja, extras configurables y validación de coordenadas delivery |

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
- El panel administrativo antiguo redirige al panel vigente para evitar presentar métricas estáticas de demostración.
- Las recomendaciones del cliente se calculan localmente con historial y ventas; no se envían datos a un proveedor de IA externo.
- La base SQLite de desarrollo quedó inicializada sin ventas, pedidos, mesas ocupadas ni turno ficticios. Las bases anteriores se respaldaron antes del reinicio.

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
