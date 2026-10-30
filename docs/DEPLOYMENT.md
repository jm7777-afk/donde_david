# Despliegue y configuración por entorno

## Desarrollo local

1. Crea un entorno virtual e instala `requirements.txt`.
2. Copia `.env.example` a `.env` y conserva `ENVIRONMENT=development`.
3. Usa SQLite local; en este entorno se crean las tablas y se cargan las cuentas demo idempotentemente.
4. Inicia con `python -m backend.app.main`.

El servidor usa el valor de `PORT` si se proporciona (por defecto, `8000`). Las contraseñas nuevas deben tener al menos 12 caracteres.

## Producción

Producción requiere PostgreSQL, una clave JWT aleatoria propia de al menos 32 caracteres y orígenes CORS HTTPS exactos. El inicio falla explícitamente si falta alguna de estas condiciones o si se configura SQLite o el comodín CORS.

Variables requeridas:

| Variable | Uso |
|---|---|
| `ENVIRONMENT=production` | Activa restricciones productivas y evita el seed |
| `DATABASE_URL` | URL PostgreSQL persistente; `postgres://` y `postgresql://` se normalizan al driver psycopg |
| `SECRET_KEY` | Clave JWT secreta, única y aleatoria |
| `ALLOWED_ORIGINS` | Lista separada por comas de orígenes exactos |
| `PORT` | Puerto asignado por la plataforma |
| `BCV_RATE_API_URL` | Feed JSON de referencia de tasa oficial; por defecto apunta al endpoint de DolarApi |

El feed de tasa es externo y no está operado directamente por el BCV. Si deja de responder, el sistema conserva la última tasa válida; el administrador también puede guardar una tasa manual, que permanece activa hasta una actualización manual del feed.

El esquema se administra con Alembic. Para una instalación nueva: `alembic upgrade head`. No uses `create_all` ni el seed demo en producción. Crea la primera cuenta admin mediante `/setup` y cambia las credenciales iniciales de desarrollo que sigan presentes en bases locales.

En Render, consulta [RENDER_DEPLOYMENT.md](../RENDER_DEPLOYMENT.md) para configurar PostgreSQL, secretos, health checks y el comando de arranque.

## Operación y escalado

- `/health` es un chequeo liviano de proceso; `/ready` verifica la base y devuelve 503 en caso de fallo.
- Los errores internos se registran en servidor y el cliente recibe un mensaje genérico.
- Uploads limitados a 5 MB con verificación de firma y tipo. Usa almacenamiento de objetos antes de depender de imágenes locales en despliegues efímeros.
- Rate limiting protege login, registro, recuperación y verificación OTP. El almacenamiento es en memoria por proceso; mantener un worker o migrar el limitador a Redis antes de escalar.
- Los WebSockets también usan memoria local. Un despliegue multiworker/multinstancia necesita un broker compartido para difundir eventos.
- Haz respaldos probados de PostgreSQL y define un procedimiento de restauración antes de operar con datos reales.
