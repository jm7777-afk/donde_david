"""
Módulo API: Copias de Seguridad y Recuperación (Admin Backups Router)
=====================================================================
Permite la generación, descarga, restauración y eliminación segura de
copias de seguridad de la base de datos para garantizar la continuidad operativa.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_roles
from backend.app.models.usuario import Usuario
from backend.app.schemas.schemas import BackupOut, BackupCreateRequest, BackupRestoreResponse
from backend.app.services.backup_service import (
    create_database_backup,
    list_backups,
    get_backup_path,
    delete_backup_file,
    restore_database_backup
)
from backend.app.services.audit_service import record_audit
from backend.app.services.db_format_service import format_database_records
from backend.app.websockets.manager import ws_manager

router = APIRouter(prefix="/admin/backups", tags=["Administración - Copias de Seguridad (Backups)"])


@router.get("", response_model=List[BackupOut])
def listar_copias_seguridad(
    current_user: Usuario = Depends(require_roles(["admin", "supervisor"]))
):
    """Retorna la lista de todas las copias de seguridad disponibles con metadatos e integridad."""
    return list_backups()


@router.post("/crear", response_model=BackupOut, status_code=status.HTTP_201_CREATED)
def crear_copia_seguridad(
    payload: BackupCreateRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["admin"]))
):
    """
    Genera de inmediato una copia de seguridad consistente de la base de datos actual.
    Registra automáticamente el evento en la auditoría del sistema.
    """
    try:
        manifest = create_database_backup(
            db=db,
            usuario=current_user.nombre_usuario,
            descripcion=payload.descripcion
        )

        record_audit(
            db=db,
            accion="BACKUP_CREATED",
            usuario=current_user.nombre_usuario,
            usuario_id=current_user.id,
            recurso="sistema_backups",
            recurso_id=manifest["filename"],
            detalle=f"Respaldo generado exitosamente ({manifest['size_human']}, SHA: {manifest['sha256'][:10]}...)",
            datos_nuevos=manifest
        )

        return manifest
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar la copia de seguridad: {str(exc)}"
        )


@router.get("/{filename}/descargar")
def descargar_copia_seguridad(
    filename: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["admin"]))
):
    """
    Descarga autenticada y segura de un archivo de respaldo específico.
    Protegido contra ataques de Directory Traversal.
    """
    try:
        file_path = get_backup_path(filename)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    record_audit(
        db=db,
        accion="BACKUP_DOWNLOADED",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="sistema_backups",
        recurso_id=filename,
        detalle=f"Descarga de archivo de respaldo {filename}"
    )

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream"
    )


@router.post("/{filename}/restaurar", response_model=BackupRestoreResponse)
def restaurar_copia_seguridad(
    filename: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["admin"]))
):
    """
    Restaura la base de datos a partir de una copia de seguridad seleccionada.
    Crea automáticamente un punto de control previo antes de sobrescribir los datos.
    """
    try:
        result = restore_database_backup(
            db=db,
            filename=filename,
            usuario=current_user.nombre_usuario
        )

        record_audit(
            db=db,
            accion="BACKUP_RESTORED",
            usuario=current_user.nombre_usuario,
            usuario_id=current_user.id,
            recurso="sistema_backups",
            recurso_id=filename,
            detalle=f"Base de datos restaurada desde {filename}. Checkpoint previo: {result.get('checkpoint_previo')}",
            datos_nuevos=result
        )

        return result
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fallo durante la restauración de la base de datos: {str(exc)}"
        )


@router.delete("/{filename}")
def eliminar_copia_seguridad(
    filename: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["admin"]))
):
    """Elimina permanentemente un archivo de respaldo específico y sus metadatos."""
    try:
        success = delete_backup_file(filename)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El archivo de respaldo '{filename}' no existe."
            )

        record_audit(
            db=db,
            accion="BACKUP_DELETED",
            usuario=current_user.nombre_usuario,
            usuario_id=current_user.id,
            recurso="sistema_backups",
            recurso_id=filename,
            detalle=f"Archivo de respaldo eliminado: {filename}"
        )

        return {"mensaje": f"Copia de seguridad '{filename}' eliminada exitosamente."}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class FormatDatabaseRequest(BaseModel):
    confirmacion: str = Field(min_length=1, max_length=32)


@router.post("/formatear-bd")
async def formatear_base_datos(
    payload: FormatDatabaseRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["admin"])),
):
    """Formatea los registros de negocio y catálogo conservando al administrador activo."""
    if payload.confirmacion.strip().upper() != "FORMATEAR":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Debes escribir exactamente 'FORMATEAR' para confirmar el reinicio de datos.",
        )

    checkpoint_name = None
    try:
        manifest = create_database_backup(
            db=db,
            usuario=current_user.nombre_usuario,
            descripcion="Respaldo previo automático antes de formatear la BD",
        )
        checkpoint_name = manifest.get("filename")
    except Exception:
        checkpoint_name = None

    deleted = format_database_records(db, preserve_admin_id=current_user.id)
    record_audit(
        db=db,
        accion="DATABASE_FORMATTED",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="sistema_bd",
        recurso_id="all",
        detalle=f"Base de datos formateada por {current_user.nombre_usuario}. Checkpoint: {checkpoint_name or 'N/A'}",
        datos_nuevos=deleted,
    )
    await ws_manager.broadcast("PRODUCTOS_ACTUALIZADOS", {"formatted": True})
    await ws_manager.broadcast("PROMOCIONES_ACTUALIZADAS", {"formatted": True})
    return {
        "mensaje": "Todos los registros de la base de datos fueron formateados correctamente.",
        "checkpoint_previo": checkpoint_name,
        "eliminados": deleted,
    }
