import sys
import os
import asyncio
import json
import logging
from contextlib import asynccontextmanager

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
import uvicorn
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from jose import JWTError, jwt
from sqlalchemy import text
from backend.app.core.config import settings
from backend.app.core.database import Base, engine, SessionLocal
from backend.app.core.rate_limit import limiter
from backend.app.core.logging_config import setup_logging
from backend.app.core.logging_middleware import RequestLoggingMiddleware
from backend.app import models
from backend.app.models.usuario import Usuario
from backend.app.api import auth, cliente, cocina, caja, admin, mesero, setup, delivery, gerencia, admin_auditoria, admin_logs, admin_backups
from backend.app.api.setup import check_system_installed, LOCK_FILE_PATH
from backend.app.websockets.manager import ws_manager
from backend.scripts.seed_data import seed

# Inicializar logging centralizado con rotación de archivos
setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT != "production":
        Base.metadata.create_all(bind=engine)
        seed()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API para la automatización de pedidos en restaurante con QR, tiempo real y turnos de caja",
    lifespan=lifespan
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# GZip Middleware para compresión ultrarrápida de respuestas HTTP
app.add_middleware(GZipMiddleware, minimum_size=500)

# Middleware de registro estructurado y métricas de latencia HTTP
app.add_middleware(RequestLoggingMiddleware)

# CORS Middleware configurado dinámicamente según entorno
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS_LIST,
    allow_credentials=True if settings.ALLOWED_ORIGINS_LIST != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(setup.router, prefix=settings.API_V1_STR)
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(cliente.router, prefix=settings.API_V1_STR)
app.include_router(cocina.router, prefix=settings.API_V1_STR)
app.include_router(caja.router, prefix=settings.API_V1_STR)
app.include_router(admin.router, prefix=settings.API_V1_STR)
app.include_router(admin_auditoria.router, prefix=settings.API_V1_STR)
app.include_router(admin_logs.router, prefix=settings.API_V1_STR)
app.include_router(admin_backups.router, prefix=settings.API_V1_STR)
app.include_router(mesero.router, prefix=settings.API_V1_STR)
app.include_router(delivery.router, prefix=settings.API_V1_STR)
app.include_router(gerencia.router, prefix=settings.API_V1_STR)

# Global Exception Handler para capturar errores no controlados
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request error for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del servidor."}
    )

# Caché en memoria una vez confirmada la instalación permanente en producción/desarrollo
_system_installed_cached = False


# Middleware Guardia de Instalación Única (/setup Guard)
@app.middleware("http")
async def setup_installer_guard_middleware(request: Request, call_next):
    global _system_installed_cached
    path = request.url.path
    
    # Excluir archivos estáticos, endpoints de API, healthcheck y websockets
    is_static_asset = (
        path.startswith("/static/")
        or path.startswith("/api/")
        or path.startswith("/ws")
        or path in {"/health", "/ready"}
    )
    
    if is_static_asset:
        response = await call_next(request)
        if (
            path.endswith(".css")
            or path.endswith(".js")
            or path.endswith(".html")
            or path.endswith(".json")
            or "sw.js" in path
        ):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    if os.path.exists(LOCK_FILE_PATH):
        is_installed = True
    elif _system_installed_cached and settings.ENVIRONMENT != "testing":
        is_installed = True
    else:
        db = SessionLocal()
        try:
            is_installed = check_system_installed(db)
            if is_installed and settings.ENVIRONMENT != "testing":
                _system_installed_cached = True
        finally:
            db.close()

    is_setup_route = path == "/setup" or path.startswith("/static/setup")

    # Si NO está instalado y quiere entrar a cualquier otra página -> Redirigir a /setup
    if not is_installed and not is_setup_route:
        return RedirectResponse(url="/setup")

    # Si YA está instalado e intenta entrar a /setup -> 403 Forbidden
    if is_installed and is_setup_route:
        return JSONResponse(
            status_code=403,
            content={"detail": "Acceso 403 Prohibido: El sistema ya se encuentra instalado. Esta ruta ha sido bloqueada permanentemente."}
        )

    return await call_next(request)

# WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        auth_message = await asyncio.wait_for(websocket.receive_text(), timeout=5)
        auth_payload = json.loads(auth_message)
        token = auth_payload.get("token") if isinstance(auth_payload, dict) else None
        if not isinstance(token, str) or not token:
            await websocket.close(code=4401, reason="Authentication required")
            return
        try:
            token_payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            await websocket.close(code=4401, reason="Invalid or expired token")
            return

        username = token_payload.get("sub")
        if not isinstance(username, str) or not username:
            await websocket.close(code=4401, reason="Invalid token")
            return

        db = SessionLocal()
        try:
            user = db.query(Usuario).filter(
                Usuario.nombre_usuario == username,
                Usuario.activo == True
            ).first()
            if not user or user.rol not in ["admin", "supervisor", "gerente", "caja", "cocina", "mesero", "repartidor"]:
                await websocket.close(code=4403, reason="Staff access required")
                return
        finally:
            db.close()

        await ws_manager.connect(websocket, accepted=True)
        while True:
            await websocket.receive_text()
    except asyncio.TimeoutError:
        await websocket.close(code=4408, reason="Authentication timeout")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except json.JSONDecodeError:
        await websocket.close(code=4401, reason="Invalid authentication message")
    except Exception:
        logger.exception("Unexpected WebSocket error.")
        ws_manager.disconnect(websocket)

# Mount static files
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../static"))
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

@app.get("/setup")
def setup_redirect():
    return RedirectResponse(url="/static/setup/index.html")

@app.get("/login")
def login_redirect():
    return RedirectResponse(url="/static/login.html")

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/health")
def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME, "version": settings.VERSION, "environment": settings.ENVIRONMENT}

@app.get("/ready")
def readiness_check():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "connected",
            "app": settings.PROJECT_NAME
        }
    except Exception:
        logger.exception("Readiness database check failed.")
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "unavailable",
                "app": settings.PROJECT_NAME
            }
        )
    finally:
        db.close()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    is_dev = os.getenv("ENVIRONMENT", "development").lower() == "development"
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port, reload=is_dev)
