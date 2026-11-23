"""
Middleware de Registro HTTP de Alto Rendimiento (Request Logging Middleware)
==========================================================================
Captura la latencia, código de estado, IP cliente y excepciones de cada petición HTTP.
Filtra activos estáticos no críticos para mantener logs limpios y de alto valor operativo.
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("donde_david.http")

# Prefijos estáticos que se omiten en logs normales para evitar ruido
STATIC_PREFIXES = ("/static/css", "/static/js", "/static/images", "/static/img", "/static/uploads", "/favicon.ico")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware para interceptar y registrar métricas de peticiones HTTP en tiempo de ejecución."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        is_static = any(path.startswith(prefix) for prefix in STATIC_PREFIXES)

        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"

        # Headers comunes detrás de proxies reversos (Render, Cloudflare, Nginx)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            status_code = response.status_code

            # Omitir logs normales de estáticos si fueron exitosos (200/304)
            if is_static and status_code < 400:
                return response

            log_msg = f"{request.method} {path} -> {status_code} [{duration_ms}ms] (IP: {client_ip})"

            if status_code >= 500:
                logger.error(log_msg)
            elif status_code >= 400:
                logger.warning(log_msg)
            else:
                logger.info(log_msg)

            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception("EXCEPCIÓN NO CONTROLADA: %s %s tras %sms (IP: %s): %s", request.method, path, duration_ms, client_ip, exc)
            raise exc
