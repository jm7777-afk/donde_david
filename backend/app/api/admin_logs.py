"""
Módulo API: Observabilidad y Logs del Servidor (Admin Logs Router)
==================================================================
Provee endpoints administrativos para la lectura en vivo de logs estructurados,
visualización de métricas de errores, descarga y rotación de archivos.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from backend.app.core.security import require_roles
from backend.app.models.usuario import Usuario
from backend.app.schemas.schemas import LogResponseOut, LogStatsOut
from backend.app.services.log_service import (
    get_system_logs,
    get_log_statistics,
    clear_system_logs,
    APP_LOG_PATH,
    ERROR_LOG_PATH
)

router = APIRouter(prefix="/admin/logs", tags=["Administración - Logs y Observabilidad"])


@router.get("", response_model=LogResponseOut)
def ver_logs(
    level: Optional[str] = Query(default=None, description="Filtrar por nivel: ALL, INFO, WARNING, ERROR, CRITICAL"),
    search: Optional[str] = Query(default=None, description="Búsqueda de texto en el mensaje"),
    limit: int = Query(default=200, ge=10, le=1000, description="Cantidad de líneas a retornar"),
    only_errors: bool = Query(default=False, description="Consultar únicamente archivo de errores críticos"),
    current_user: Usuario = Depends(require_roles(["admin", "supervisor", "gerente"]))
):
    """
    Retorna las líneas de log más recientes parseadas de forma estructurada.
    Permite filtrar por nivel de gravedad o término de búsqueda en tiempo real.
    """
    result = get_system_logs(level=level, search=search, limit=limit, only_errors=only_errors)
    return result


@router.get("/stats", response_model=LogStatsOut)
def obtener_estadisticas_logs(
    current_user: Usuario = Depends(require_roles(["admin", "supervisor", "gerente"]))
):
    """
    Retorna métricas agregadas de salud del sistema basadas en los logs:
    distribución de niveles de eventos, porcentaje de error y tamaño de archivos.
    """
    return get_log_statistics()


@router.get("/download")
def descargar_archivo_log(
    tipo: str = Query(default="app", pattern="^(app|error)$", description="Tipo de log a descargar: 'app' o 'error'"),
    current_user: Usuario = Depends(require_roles(["admin", "supervisor"]))
):
    """Descarga de forma segura el archivo de registro en bruto."""
    target_path = ERROR_LOG_PATH if tipo == "error" else APP_LOG_PATH
    if not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El archivo de log '{target_path.name}' todavía no contiene datos."
        )

    return FileResponse(
        path=str(target_path),
        filename=target_path.name,
        media_type="text/plain"
    )


@router.delete("/clear")
def limpiar_logs(
    current_user: Usuario = Depends(require_roles(["admin"]))
):
    """
    Trunca los archivos de registro activos.
    Operación restringida exclusivamente al Super Administrador.
    """
    success = clear_system_logs()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudieron truncar los archivos de log."
        )
    return {"mensaje": "Archivos de log reseteados exitosamente."}
