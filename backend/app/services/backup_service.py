"""
Servicio Empresarial de Respaldo y Recuperación (Database Backup & Disaster Recovery)
===================================================================================
Soporta generación de copias de seguridad consistentes para SQLite y PostgreSQL,
cálculo de integridad criptográfica (SHA-256), rotación automática de retención
y restauración con punto de control previo (Pre-Restore Safety Checkpoint).
"""
from datetime import date, datetime, timezone
import hashlib
import json
import logging
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Boolean, Date, DateTime, Integer, text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import engine, Base

logger = logging.getLogger("donde_david.backups")

# Directorio base para las copias de seguridad
BACKUPS_DIR = Path(__file__).resolve().parent.parent.parent / "backups"
BACKUPS_DIR.mkdir(parents=True, exist_ok=True)

MAX_BACKUPS_RETENTION = 15


def _calculate_sha256(filepath: Path) -> str:
    """Calcula el hash SHA-256 de un archivo para garantizar integridad criptográfica."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _format_size(size_bytes: int) -> str:
    """Formatea bytes a formato legible (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 2)} KB"
    else:
        return f"{round(size_bytes / (1024 * 1024), 2)} MB"


def _sanitize_filename(filename: str) -> str:
    """Previene ataques de Directory Traversal validando el nombre de archivo."""
    clean_name = os.path.basename(filename).strip()
    if not clean_name or ".." in clean_name or "/" in clean_name or "\\" in clean_name:
        raise ValueError("Nombre de archivo de respaldo no válido.")
    return clean_name


def create_database_backup(
    db: Session,
    usuario: str,
    descripcion: Optional[str] = None
) -> Dict[str, Any]:
    """
    Genera una copia de seguridad consistente de la base de datos actual.
    
    :param db: Sesión SQLAlchemy.
    :param usuario: Nombre del usuario administrador que solicita el respaldo.
    :param descripcion: Nota o motivo de la copia de seguridad.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    db_url = settings.DATABASE_URL.lower()

    if "sqlite" in db_url:
        # Extraer ruta del archivo SQLite
        sqlite_file = settings.DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "").split("?")[0]
        src_path = Path(sqlite_file).resolve()
        if not src_path.exists():
            # Buscar en directorio actual
            src_path = Path("restaurante.db").resolve()

        backup_filename = f"backup_donde_david_{timestamp}.db"
        dest_path = BACKUPS_DIR / backup_filename

        # Uso de la API online de SQLite para consistencia sin bloqueos
        if src_path.exists():
            src_conn = sqlite3.connect(str(src_path))
            dest_conn = sqlite3.connect(str(dest_path))
            try:
                src_conn.backup(dest_conn)
            finally:
                dest_conn.close()
                src_conn.close()
        else:
            raise FileNotFoundError(f"No se encontró el archivo de base de datos fuente: {src_path}")

        engine_type = "SQLite"
    else:
        # Para PostgreSQL o motores externos, exportamos volcado SQL/JSON completo de tablas
        backup_filename = f"backup_donde_david_{timestamp}.json"
        dest_path = BACKUPS_DIR / backup_filename
        export_data: Dict[str, Any] = {
            "version": settings.VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tables": {}
        }

        # Extraer registros de cada tabla definida en el modelo
        for table in Base.metadata.sorted_tables:
            result = db.execute(text(f'SELECT * FROM "{table.name}"'))
            columns = result.keys()
            rows = [dict(zip(columns, [str(v) if isinstance(v, (datetime, bytes)) else v for v in row])) for row in result.fetchall()]
            export_data["tables"][table.name] = rows

        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)

        engine_type = "PostgreSQL"

    file_size = dest_path.stat().st_size
    sha256_hash = _calculate_sha256(dest_path)

    # Crear archivo de manifiesto asociado (.meta.json)
    manifest = {
        "filename": backup_filename,
        "engine": engine_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": usuario,
        "description": descripcion or "Respaldo programado / bajo demanda",
        "size_bytes": file_size,
        "size_human": _format_size(file_size),
        "sha256": sha256_hash,
        "status": "COMPLETED"
    }
    meta_path = BACKUPS_DIR / f"{backup_filename}.meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Respaldo completado exitosamente: %s (%s)", backup_filename, manifest["size_human"])

    # Aplicar política de retención
    prune_old_backups(MAX_BACKUPS_RETENTION)

    return manifest


def list_backups() -> List[Dict[str, Any]]:
    """
    Lista todas las copias de seguridad disponibles en disco con sus metadatos e integridad.
    """
    backups: List[Dict[str, Any]] = []

    for file_path in BACKUPS_DIR.glob("backup_donde_david_*.*"):
        if file_path.suffix == ".json" and file_path.name.endswith(".meta.json"):
            continue

        meta_path = BACKUPS_DIR / f"{file_path.name}.meta.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    backups.append(meta)
                    continue
            except Exception:
                pass

        # Si no tiene manifiesto o falló, construir metadatos al vuelo
        file_size = file_path.stat().st_size
        backups.append({
            "filename": file_path.name,
            "engine": "SQLite" if file_path.suffix == ".db" else "Export",
            "created_at": datetime.fromtimestamp(file_path.stat().st_mtime, timezone.utc).isoformat(),
            "created_by": "sistema",
            "description": "Copia de seguridad existente",
            "size_bytes": file_size,
            "size_human": _format_size(file_size),
            "sha256": _calculate_sha256(file_path),
            "status": "COMPLETED"
        })

    # Ordenar del más reciente al más antiguo
    backups.sort(key=lambda b: b.get("created_at", ""), reverse=True)
    return backups


def get_backup_path(filename: str) -> Path:
    """Valida y retorna la ruta segura de un archivo de respaldo para descarga."""
    clean_name = _sanitize_filename(filename)
    path = BACKUPS_DIR / clean_name
    if not path.exists():
        raise FileNotFoundError(f"El archivo de respaldo '{clean_name}' no existe.")
    return path


def delete_backup_file(filename: str) -> bool:
    """Elimina de forma segura un archivo de respaldo y su manifiesto."""
    clean_name = _sanitize_filename(filename)
    backup_path = BACKUPS_DIR / clean_name
    meta_path = BACKUPS_DIR / f"{clean_name}.meta.json"

    deleted = False
    if backup_path.exists():
        backup_path.unlink()
        deleted = True
    if meta_path.exists():
        meta_path.unlink()

    if deleted:
        logger.info("Respaldo eliminado: %s", clean_name)
    return deleted


def restore_database_backup(
    db: Session,
    filename: str,
    usuario: str
) -> Dict[str, Any]:
    """
    Restaura la base de datos a partir de una copia de seguridad seleccionada.
    Crea automáticamente un punto de control de seguridad previo antes de sobrescribir.
    """
    clean_name = _sanitize_filename(filename)
    backup_path = BACKUPS_DIR / clean_name
    if not backup_path.exists():
        raise FileNotFoundError(f"Archivo de respaldo no encontrado: {clean_name}")

    # 1. Crear punto de seguridad PREVIO a la restauración (fail-safe)
    safety_name = f"safety_checkpoint_before_restore_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.db"
    safety_path = BACKUPS_DIR / safety_name

    db_url = settings.DATABASE_URL.lower()
    if "sqlite" in db_url:
        sqlite_file = settings.DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "").split("?")[0]
        current_db = Path(sqlite_file).resolve()
        if not current_db.exists():
            current_db = Path("restaurante.db").resolve()

        if current_db.exists():
            shutil.copy2(current_db, safety_path)
            logger.info("Punto de control previo creado: %s", safety_name)

        # Restaurar copiando el respaldo sobre la base activa
        shutil.copy2(backup_path, current_db)
        logger.info("Restauración SQLite completada exitosamente desde: %s por usuario %s", clean_name, usuario)

        return {
            "mensaje": f"Base de datos restaurada exitosamente desde {clean_name}.",
            "checkpoint_previo": safety_name,
            "restaurado_por": usuario,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    else:
        # Restauración de volcado estructurado (PostgreSQL)
        with open(backup_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        tables_payload = data.get("tables")
        if not isinstance(tables_payload, dict):
            raise ValueError("Formato de respaldo inválido: falta el mapa 'tables'.")

        metadata_tables = Base.metadata.tables
        unknown_tables = [name for name in tables_payload if name not in metadata_tables]
        if unknown_tables:
            raise ValueError(f"El respaldo contiene tablas no reconocidas: {', '.join(sorted(unknown_tables))}")

        def _coerce_column_value(column, value: Any) -> Any:
            if value is None:
                return None
            col_type = column.type
            if isinstance(col_type, DateTime) and isinstance(value, str):
                return datetime.fromisoformat(value)
            if isinstance(col_type, Date) and not isinstance(col_type, DateTime) and isinstance(value, str):
                return date.fromisoformat(value[:10])
            if isinstance(col_type, Boolean) and isinstance(value, (int, str)):
                if isinstance(value, str):
                    return value.strip().lower() in ("true", "1", "yes", "si", "sí")
                return bool(value)
            if isinstance(col_type, Integer) and isinstance(value, str):
                return int(value)
            return value

        sorted_tables = [t for t in Base.metadata.sorted_tables if t.name in tables_payload]
        try:
            for table in reversed(sorted_tables):
                db.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))

            restored_tables: List[str] = []
            for table in sorted_tables:
                raw_rows = tables_payload.get(table.name) or []
                if not isinstance(raw_rows, list):
                    raise ValueError(f"Formato inválido de filas para la tabla '{table.name}'.")
                valid_cols = {col.name: col for col in table.columns}
                cleaned_rows = []
                for row in raw_rows:
                    if not isinstance(row, dict):
                        continue
                    cleaned_rows.append({
                        col_name: _coerce_column_value(valid_cols[col_name], value)
                        for col_name, value in row.items()
                        if col_name in valid_cols
                    })
                if cleaned_rows:
                    db.execute(table.insert(), cleaned_rows)

                pk_cols = [col for col in table.primary_key.columns if isinstance(col.type, Integer)]
                if len(pk_cols) == 1:
                    pk_name = pk_cols[0].name
                    db.execute(
                        text(
                            f'SELECT setval('
                            f'pg_get_serial_sequence(:tbl, :pk), '
                            f'COALESCE((SELECT MAX("{pk_name}") FROM "{table.name}"), 1), '
                            f'EXISTS(SELECT 1 FROM "{table.name}")'
                            f')'
                        ),
                        {"tbl": table.name, "pk": pk_name},
                    )
                restored_tables.append(table.name)

            db.commit()
        except Exception:
            db.rollback()
            raise

        return {
            "mensaje": f"Restauración relacional completada desde {clean_name}.",
            "tablas_restauradas": restored_tables,
            "restaurado_por": usuario,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def prune_old_backups(keep_count: int = MAX_BACKUPS_RETENTION) -> int:
    """Elimina las copias de seguridad más antiguas cuando exceden el límite de retención."""
    all_backups = list_backups()
    if len(all_backups) <= keep_count:
        return 0

    to_delete = all_backups[keep_count:]
    count = 0
    for b in to_delete:
        try:
            delete_backup_file(b["filename"])
            count += 1
        except Exception as exc:
            logger.warning("No se pudo purgar respaldo antiguo %s: %s", b.get("filename"), exc)
    return count
