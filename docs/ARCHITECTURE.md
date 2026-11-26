# Arquitectura de Dónde David

## Alcance y componentes

El repositorio contiene dos clientes independientes que consumen el mismo backend:

```text
backend/
  app/
    api/          Rutas FastAPI por dominio
    core/         Configuración, base de datos, seguridad y rate limiting
    models/       Entidades SQLAlchemy
    schemas/      Contratos y validación Pydantic
    services/     Lógica compartida extraída de las rutas
    websockets/   Gestión de conexiones y eventos en tiempo real
  static/
    cliente/ admin/ caja/ cocina/ mesero/ delivery/ gerencia/ setup/
    css/ js/
mobile_app/
  lib/core/ models/ providers/ screens/ widgets/
```

- **Backend:** FastAPI, SQLAlchemy y Pydantic. SQLite se usa por defecto en desarrollo; producción exige PostgreSQL, una clave de firma segura y orígenes CORS explícitos.
- **Web:** páginas HTML por rol, CSS compartido y JavaScript sin framework. No es una SPA única.
- **Móvil:** aplicación Flutter multiplataforma con servicios, modelos, providers, pantallas y widgets propios. Comparte la API, no código de interfaz con la web.
- **Persistencia y despliegue:** las migraciones Alembic son el mecanismo de evolución del esquema; la base local no debe usarse como sustituto de migraciones ni incluirse como dato de prueba.

## Recorrido de una petición

```text
Web / Flutter
    -> API REST / WebSocket autenticado
    -> router del dominio
    -> servicio compartido (cuando existe)
    -> modelo SQLAlchemy y sesión
    -> SQLite local o PostgreSQL en producción
```

Los routers actuales se organizan por autenticación, cliente, cocina, caja, administración, mesero, delivery, gerencia y configuración inicial. `main.py` registra esos routers, middleware, archivos estáticos y el endpoint WebSocket. La autorización y el recálculo de operaciones sensibles deben permanecer en el servidor.

## Tiempo real

El endpoint `/ws` autentica al personal antes de registrar la conexión en el administrador de WebSockets. Los clientes reciben eventos de pedidos y cambios operativos; las operaciones persistentes continúan realizándose mediante la API y la base de datos. WebSocket es un canal de notificación, no una fuente de verdad distinta de la base de datos.

## Estado actual y deuda técnica conocida

- Los routers de administración, caja y cliente concentran los módulos API más grandes; la lógica transaccional compartida de pedidos, cálculo de precios, extras y bloqueo determinista de inventario se centralizó en `backend/app/services/orders.py`. Conservar los contratos HTTP y sus pruebas al refactorizar otros flujos.
- Los 10 bloques `<style>` de las páginas HTML ya se movieron a hojas externas; el login también quedó sin atributos de estilo. Restan estilos inline puntuales en páginas heredadas y plantillas JavaScript, donde las interpolaciones de usuario y datos dinámicos ya utilizan funciones de escape HTML (`escapeAdminHtml`, `escapeCajaHtml`, `escapeKdsHtml`, `escapeMeseroHtml`, `escapeDeliveryText`, `escapeClientHtml`).
- Los módulos JavaScript de cliente, caja y administración son los más extensos. Mantienen integración con páginas existentes, por lo que su división debe conservar orden de carga, funciones usadas desde HTML y estado compartido.
- El límite de peticiones (`slowapi`) y los canales WebSocket (`ws_manager`) operan en memoria local; por ello `render.yaml` ejecuta Gunicorn con `--workers 1` hasta incorporar un broker Redis compartido.
- Algunas pantallas Flutter son grandes. Ya existen límites funcionales en `screens/`, `providers/` y `widgets/`; conviene extraer componentes y lógica de estado en cambios pequeños cubiertos por pruebas.
- La CI (`.github/workflows/ci.yml`) ejecuta `compileall`, `node --check` sobre `backend/static/js/`, `alembic upgrade head && alembic check`, `pytest tests -q` y análisis/pruebas Flutter (`flutter analyze` / `flutter test`).

## Convenciones para cambios

1. Mantener rutas, esquemas, roles, eventos y reglas de negocio compatibles salvo cambio solicitado y probado.
2. Separar responsabilidades por dominio; reutilizar `services/` (`orders.py`, `audit_service.py`, `backup_service.py`, `tables.py`, `loyalty.py`) para reglas financieras e inventario.
3. En web, ubicar CSS en `backend/static/css/`, JavaScript en `backend/static/js/`, actualizar `?v=5.3` / caché PWA (`sw.js`) ante cambios de assets y evitar atributos `style` o bloques `<style>` en HTML.
4. En Flutter, mantener widgets de presentación separados de acceso a API, persistencia y estado; evitar que las pantallas creen directamente múltiples clientes HTTP o sesiones.
5. Validar backend con `pytest tests -v`, `alembic check` y `node --check`; validar móvil desde `mobile_app/` con `flutter analyze --no-pub` y `flutter test --no-pub`.
6. No versionar bases locales (`restaurante.db` desindexado de Git), secretos, cachés ni resultados de compilación. Mantener los archivos de bloqueo de dependencias y las migraciones.

## Orden recomendado de evolución

1. Asegurar que ambas aplicaciones y sus fuentes sean visibles para Git y que los artefactos generados estén ignorados.
2. Añadir análisis y pruebas Flutter a CI y automatizar comprobaciones web sin impedir la migración gradual.
3. Migrar CSS por pantalla con clases semánticas y validación visual; comenzar por el flujo de cliente y continuar con caja y administración.
4. Dividir los módulos JavaScript grandes por dominio y los routers grandes por casos de uso, con pruebas de regresión antes de mover lógica.
5. Añadir pruebas de navegador para checkout, cobro/validación de pago y operaciones principales de administración.
