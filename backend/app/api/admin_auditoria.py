"""
Módulo API: Auditoría y Trazabilidad Administrativa (Admin Audit Router)
========================================================================
Provee endpoints seguros para la consulta, filtrado, detalle y exportación
de los eventos de auditoría y trazabilidad del sistema Donde David.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_roles
from backend.app.models.usuario import Usuario
from backend.app.schemas.schemas import AuditoriaOut, AuditoriaListOut
from backend.app.services.audit_service import (
    get_audit_logs,
    get_distinct_actions,
    get_distinct_resources,
    generate_audit_csv
)

router = APIRouter(prefix="/admin/auditoria", tags=["Administración - Auditoría y Trazabilidad"])


@router.get("", response_model=AuditoriaListOut)
def listar_auditoria(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    usuario: Optional[str] = Query(default=None),
    accion: Optional[str] = Query(default=None),
    recurso: Optional[str] = Query(default=None),
    fecha_desde: Optional[datetime] = Query(default=None),
    fecha_hasta: Optional[datetime] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["admin", "supervisor", "gerente"]))
):
    """
    Obtiene la lista paginada de eventos de auditoría con filtros avanzados
    por usuario, código de acción, recurso, rango de fechas y búsqueda textual.
    """
    items, total = get_audit_logs(
        db=db,
        skip=skip,
        limit=limit,
        usuario=usuario,
        accion=accion,
        recurso=recurso,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        search=search
    )
    acciones = get_distinct_actions(db)
    recursos = get_distinct_resources(db)

    return {
        "total": total,
        "items": items,
        "acciones_disponibles": acciones,
        "recursos_disponibles": recursos
    }


@router.get("/acciones", response_model=list[str])
def obtener_acciones_auditoria(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["admin", "supervisor", "gerente"]))
):
    """Retorna el catálogo de tipos de acciones únicas registradas en auditoría."""
    return get_distinct_actions(db)


@router.get("/recursos", response_model=list[str])
def obtener_recursos_auditoria(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["admin", "supervisor", "gerente"]))
):
    """Retorna el catálogo de entidades/recursos únicos auditados en el sistema."""
    return get_distinct_resources(db)


@router.get("/export", response_class=PlainTextResponse)
def exportar_auditoria_csv(
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_roles(["admin", "supervisor"]))
):
    """
    Exporta los registros de auditoría en formato CSV para cumplimiento legal,
    informes periciales o análisis externo en hojas de cálculo.
    """
    items, _ = get_audit_logs(db=db, skip=0, limit=limit)
    csv_data = generate_audit_csv(items)

    filename = f"auditoria_donde_david_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
