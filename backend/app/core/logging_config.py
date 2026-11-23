"""
Configuración Centralizada de Logging para Producción y Desarrollo
==================================================================
Implementa rotación automática de archivos por tamaño (RotatingFileHandler),
separación de logs operativos y logs de errores críticos, y formateo estructurado.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Directorio base para los logs del sistema
LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

APP_LOG_PATH = LOGS_DIR / "donde_david.log"
ERROR_LOG_PATH = LOGS_DIR / "donde_david_errors.log"

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(level: str = "INFO") -> None:
    """
    Configura el sistema de registro de la aplicación.
    Inicializa los handlers de consola y los archivos rotativos de 5MB con 5 copias de respaldo.
    """
    global _configured
    if _configured:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    # 1. Handler para Consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    # 2. Handler rotativo para todos los eventos generales (Max 5MB x 5 backups)
    app_file_handler = RotatingFileHandler(
        filename=str(APP_LOG_PATH),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    app_file_handler.setLevel(numeric_level)
    app_file_handler.setFormatter(formatter)

    # 3. Handler rotativo exclusivo para errores y excepciones críticas (Max 5MB x 5 backups)
    error_file_handler = RotatingFileHandler(
        filename=str(ERROR_LOG_PATH),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)

    # Configurar el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remover handlers previos para evitar duplicados en recargas de uvicorn
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_file_handler)
    root_logger.addHandler(error_file_handler)

    # Configurar loggers específicos
    for module_name in ("backend", "uvicorn", "fastapi"):
        mod_logger = logging.getLogger(module_name)
        mod_logger.setLevel(numeric_level)

    _configured = True
    logging.info("Sistema de Logging Centralizado Inicializado. Directorio de logs: %s", LOGS_DIR)
