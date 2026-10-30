# Despliegue seguro en Render

## Recursos y variables

1. Crea una base PostgreSQL persistente en Render.
2. En el Web Service configura `DATABASE_URL` con la URL interna de esa base.
3. Configura `SECRET_KEY` como un valor aleatorio único de al menos 32 caracteres. Puedes generarlo localmente con `python -c "import secrets; print(secrets.token_urlsafe(48))"` y guardarlo solo en el panel de Render.
4. Configura `ALLOWED_ORIGINS` con los orígenes HTTPS exactos, separados por coma. No uses `*`.
5. Define `ENVIRONMENT=production`. No cargues un archivo `.env` ni uses credenciales demo en producción.
6. Si habilitas la selección de ubicación con Google Maps, configura la clave del navegador desde Administración. Restríngela por los dominios públicos exactos en Google Cloud y habilita solo las APIs requeridas; nunca uses una clave de servidor en el navegador.

El `render.yaml` deja `DATABASE_URL`, `SECRET_KEY` y `ALLOWED_ORIGINS` como variables privadas de configuración para evitar valores inseguros en el repositorio. El comando de inicio aplica las migraciones de Alembic antes de arrancar Gunicorn.

## Comandos del servicio

- Build: `pip install -r requirements.txt`
- Start: `alembic upgrade head && gunicorn -k uvicorn.workers.UvicornWorker --workers 1 backend.app.main:app --bind 0.0.0.0:$PORT`
- Health check: `/health`
- Readiness check: `/ready` (devuelve HTTP 503 si la base de datos no está disponible)

Se mantiene un worker porque la difusión WebSocket y el rate limiter actual viven en memoria de proceso. Antes de escalar horizontalmente, deben migrarse a un broker compartido (por ejemplo, Redis/pub-sub y rate limit distribuido).

## Base de datos existente

Las migraciones automáticas están destinadas a una base vacía nueva. Para una base ya existente, haz primero un respaldo, compara el esquema real con los modelos y define una migración de adopción revisada antes de marcar una versión. No ejecutes `alembic stamp head` sobre una base sin verificarla.

En desarrollo, SQLite y las cuentas demo siguen disponibles. El proceso de producción no crea tablas automáticamente ni ejecuta semillas; los datos iniciales se cargan mediante el asistente de instalación y las migraciones.

La migración `f31a7b2c9d10` añade opciones y medios para productos y coordenadas para pedidos de delivery. Antes de desplegar una actualización, conserva un respaldo reciente y confirma que la base está en una revisión compatible; el comando de inicio aplica las revisiones pendientes.

## Archivos subidos

Las imágenes aceptadas tienen límite de 5 MB y se restringen a JPEG, PNG o WEBP. Render puede usar almacenamiento efímero para el filesystem local; para conservar imágenes entre despliegues, configura un almacenamiento de objetos persistente antes de usar uploads en producción.
