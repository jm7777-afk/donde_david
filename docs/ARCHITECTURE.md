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

- Los routers de administración, caja y cliente concentran los módulos API más grandes. `services/` todavía es pequeño; no se debe trasladar lógica a servicios sin conservar los contratos HTTP y sus pruebas.
- Los 10 bloques `<style>` de las páginas HTML ya se movieron a hojas externas; el login también quedó sin atributos de estilo. Restan 809 atributos `style` en 12 páginas y estilos en plantillas JavaScript. La migración elegida es semántica y gradual por pantalla, no una conversión masiva a clases opacas.
- Los módulos JavaScript de cliente, caja y administración son los más extensos. Mantienen integración con páginas existentes, por lo que su división debe conservar orden de carga, funciones usadas desde HTML y estado compartido.
- Algunas pantallas Flutter son grandes. Ya existen límites funcionales en `screens/`, `providers/` y `widgets/`; conviene extraer componentes y lógica de estado en cambios pequeños cubiertos por pruebas.
- La CI ejecuta pruebas Python y análisis/pruebas Flutter. La web ya valida que no se reintroduzcan bloques `<style>` y que el login migrado no tenga estilos inline; faltan pruebas de flujo en navegador y completar la migración de atributos.

## Convenciones para cambios

1. Mantener rutas, esquemas, roles, eventos y reglas de negocio compatibles salvo cambio solicitado y probado.
2. Separar responsabilidades por dominio; introducir servicios solo para lógica reutilizable o transacciones que necesiten pruebas independientes.
3. En web, ubicar CSS en `backend/static/css/`, JavaScript en `backend/static/js/` y usar nombres de clases descriptivos por componente/estado. Migrar una pantalla a la vez y verificar escritorio, móvil e interacciones dinámicas.
4. En Flutter, mantener widgets de presentación separados de acceso a API, persistencia y estado; evitar que las pantallas creen directamente múltiples clientes HTTP o sesiones.
5. Validar backend con `python -B -m pytest -q -p no:cacheprovider tests`; validar móvil desde `mobile_app/` con `flutter analyze --no-pub` y `flutter test --no-pub`.
6. No versionar bases locales, secretos, cachés ni resultados de compilación. Mantener los archivos de bloqueo de dependencias y las migraciones.

## Orden recomendado de evolución

1. Asegurar que ambas aplicaciones y sus fuentes sean visibles para Git y que los artefactos generados estén ignorados.
2. Añadir análisis y pruebas Flutter a CI y automatizar comprobaciones web sin impedir la migración gradual.
3. Migrar CSS por pantalla con clases semánticas y validación visual; comenzar por el flujo de cliente y continuar con caja y administración.
4. Dividir los módulos JavaScript grandes por dominio y los routers grandes por casos de uso, con pruebas de regresión antes de mover lógica.
5. Añadir pruebas de navegador para checkout, cobro/validación de pago y operaciones principales de administración.
