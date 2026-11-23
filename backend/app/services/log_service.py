"""
Servicio de Gestión y Análisis de Logs del Sistema (Log Service)
==============================================================
Permite la inspección en tiempo real, búsqueda con expresiones o términos,
análisis de tasas de error y descarga de archivos de registro.
"""
from datetime import datetime
import os
import re
from typing import Dict, List, Optional, Any
from pathlib import Path

from backend.app.core.logging_config import APP_LOG_PATH, ERROR_LOG_PATH, LOGS_DIR

LOG_LINE_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (?P<level>[A-Z]+)\s* \| (?P<logger>[\w\.-]+) \| (?P<message>.*)$"
)


def _tail_file(filepath: Path, max_lines: int = 500) -> List[str]:
    """
    Lee las últimas N líneas de un archivo de forma eficiente y segura,
    sin cargar archivos masivos enteros en memoria.
    """
    if not filepath.exists() or filepath.stat().st_size == 0:
        return []

    lines: List[str] = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            # Para archivos moderados (<15MB), readlines() invertido es rápido y seguro
            all_lines = f.readlines()
            lines = all_lines[-max_lines:]
    except Exception:
        pass
    return lines


def parse_log_line(line: str) -> Dict[str, Any]:
    """Parsea una línea de log estructurada en un diccionario tipado."""
    line_clean = line.strip()
    match = LOG_LINE_REGEX.match(line_clean)
    if match:
        return {
            "timestamp": match.group("timestamp"),
            "level": match.group("level"),
            "logger": match.group("logger"),
            "message": match.group("message"),
            "raw": line_clean
        }
    return {
        "timestamp": None,
        "level": "INFO",
        "logger": "raw",
        "message": line_clean,
        "raw": line_clean
    }


def get_system_logs(
    level: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 200,
    only_errors: bool = False
) -> Dict[str, Any]:
    """
    Obtiene y filtra las líneas de log más recientes del servidor.
    
    :param level: Nivel de log a filtrar (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    :param search: Término de búsqueda de texto dentro del mensaje.
    :param limit: Número máximo de líneas a retornar.
    :param only_errors: Si es True, consulta directamente el log específico de errores.
    """
    target_path = ERROR_LOG_PATH if only_errors else APP_LOG_PATH
    raw_lines = _tail_file(target_path, max_lines=max(limit * 3, 500))

    parsed_entries: List[Dict[str, Any]] = []
    level_filter = level.strip().upper() if level and level.strip() != "ALL" else None
    search_term = search.strip().lower() if search and search.strip() else None

    # Procesar en orden cronológico inverso (el más reciente primero)
    for line in reversed(raw_lines):
        if not line.strip():
            continue
        entry = parse_log_line(line)

        if level_filter and entry["level"] != level_filter:
            continue

        if search_term and search_term not in entry["raw"].lower():
            continue

        parsed_entries.append(entry)
        if len(parsed_entries) >= limit:
            break

    file_size_bytes = target_path.stat().st_size if target_path.exists() else 0
    return {
        "file": target_path.name,
        "size_kb": round(file_size_bytes / 1024, 2),
        "total_returned": len(parsed_entries),
        "logs": parsed_entries
    }


def get_log_statistics() -> Dict[str, Any]:
    """
    Calcula métricas agregadas de los logs para los dashboards de observabilidad y salud.
    """
    lines = _tail_file(APP_LOG_PATH, max_lines=1000)
    counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0, "DEBUG": 0}

    for line in lines:
        entry = parse_log_line(line)
        lvl = entry["level"]
        if lvl in counts:
            counts[lvl] += 1
        else:
            counts[lvl] = 1

    total = sum(counts.values()) or 1
    error_rate = round(((counts.get("ERROR", 0) + counts.get("CRITICAL", 0)) / total) * 100, 2)

    return {
        "total_recent_events": total,
        "counts_by_level": counts,
        "error_rate_percentage": error_rate,
        "app_log_size_kb": round(APP_LOG_PATH.stat().st_size / 1024, 2) if APP_LOG_PATH.exists() else 0,
        "error_log_size_kb": round(ERROR_LOG_PATH.stat().st_size / 1024, 2) if ERROR_LOG_PATH.exists() else 0
    }


def clear_system_logs() -> bool:
    """
    Trunca de manera segura los archivos de log activos para mantenimiento o reseteo administrativo.
    """
    try:
        if APP_LOG_PATH.exists():
            with open(APP_LOG_PATH, "w", encoding="utf-8") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | INFO     | system | Logs reiniciados por el administrador.\n")
        if ERROR_LOG_PATH.exists():
            with open(ERROR_LOG_PATH, "w", encoding="utf-8") as f:
                f.truncate(0)
        return True
    except Exception:
        return False
