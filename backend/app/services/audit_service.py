"""
Servicio Empresarial de Auditoría y Trazabilidad (Audit Service)
==============================================================
Provee funciones robustas para el registro, consulta, filtrado y exportación
de eventos de auditoría en la plataforma Donde David.
Diseñado bajo el principio de no interferencia (fail-safe): los fallos en auditoría
no bloquean las transacciones operativas principales del restaurante.
"""
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from sqlalchemy import or_, desc
from sqlalchemy.orm import Session

from backend.app.models.auditoria import Auditoria

logger = logging.getLogger("donde_david.audit")


def _serialize_payload(data: Any) -> Optional[str]:
    """Serializa estructuras de datos complejas a formato JSON para trazabilidad."""
    if data is None:
        return None
    if isinstance(data, str):
        return data
    try:
        return json.dumps(data, default=str, ensure_ascii=False)
    except Exception as exc:
        logger.warning("No se pudo serializar el payload de auditoría: %s", exc)
        return str(data)


def record_audit(
    db: Session,
    accion: str,
    usuario: str,
    usuario_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    recurso: Optional[str] = None,
    recurso_id: Optional[Union[str, int]] = None,
    detalle: Optional[str] = None,
    datos_previos: Optional[Union[dict, list, str]] = None,
    datos_nuevos: Optional[Union[dict, list, str]] = None,
    auto_commit: bool = True,
    normalize_action: bool = True,
) -> Optional[Auditoria]:
    """
    Registra un evento de auditoría en la base de datos de manera segura y resiliente.
    
    :param db: Sesión de SQLAlchemy activa.
    :param accion: Código de acción (Ej: 'LOGIN_SUCCESS', 'PRODUCT_UPDATE', 'CASH_EXPENSE').
    :param usuario: Nombre del usuario operador o 'sistema'.
    :param usuario_id: ID opcional del usuario en la base de datos.
    :param ip_address: Dirección IP del cliente remitente.
    :param recurso: Nombre de la entidad o dominio afectado (Ej: 'productos', 'usuarios', 'pedidos').
    :param recurso_id: Identificador primario del recurso afectado.
    :param detalle: Resumen descriptivo en lenguaje natural de la acción.
    :param datos_previos: Estado previo de la entidad antes de mutar.
    :param datos_nuevos: Estado nuevo de la entidad tras mutar.
    :param auto_commit: Si es True, realiza commit inmediato; si es False, se acopla a la transacción activa.
    """
    try:
        clean_action = accion.strip()
        entry = Auditoria(
            accion=clean_action.upper() if normalize_action else clean_action,
            usuario=usuario.strip() if usuario else "desconocido",
            usuario_id=usuario_id,
            ip_address=ip_address.strip() if ip_address else None,
            recurso=recurso.strip().lower() if recurso else None,
            recurso_id=str(recurso_id) if recurso_id is not None else None,
            detalle=detalle.strip() if detalle else None,
            datos_previos=_serialize_payload(datos_previos),
            datos_nuevos=_serialize_payload(datos_nuevos),
            fecha=datetime.now(timezone.utc)
        )
        db.add(entry)
        if auto_commit:
            db.commit()
            db.refresh(entry)
        return entry
    except Exception as exc:
        logger.error("Error al persistir registro de auditoría [%s]: %s", accion, exc, exc_info=True)
        if auto_commit:
            try:
                db.rollback()
            except Exception:
                pass
        return None


def get_audit_logs(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    usuario: Optional[str] = None,
    accion: Optional[str] = None,
    recurso: Optional[str] = None,
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    search: Optional[str] = None
) -> Tuple[List[Auditoria], int]:
    """
    Obtiene registros de auditoría filtrados y paginados con cálculo del total de coincidencias.
    """
    query = db.query(Auditoria)

    if usuario and usuario.strip():
        query = query.filter(Auditoria.usuario.ilike(f"%{usuario.strip()}%"))

    if accion and accion.strip():
        query = query.filter(Auditoria.accion == accion.strip().upper())

    if recurso and recurso.strip():
        query = query.filter(Auditoria.recurso == recurso.strip().lower())

    if fecha_desde:
        query = query.filter(Auditoria.fecha >= fecha_desde)

    if fecha_hasta:
        query = query.filter(Auditoria.fecha <= fecha_hasta)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Auditoria.detalle.ilike(term),
                Auditoria.usuario.ilike(term),
                Auditoria.accion.ilike(term),
                Auditoria.recurso.ilike(term),
                Auditoria.recurso_id.ilike(term),
                Auditoria.ip_address.ilike(term)
            )
        )

    total = query.count()
    items = query.order_by(desc(Auditoria.fecha)).offset(skip).limit(limit).all()
    return items, total


def get_distinct_actions(db: Session) -> List[str]:
    """Retorna la lista ordenada de tipos de acciones únicas registradas en auditoría."""
    rows = db.query(Auditoria.accion).distinct().order_by(Auditoria.accion).all()
    return [r[0] for r in rows if r[0]]


def get_distinct_resources(db: Session) -> List[str]:
    """Retorna la lista ordenada de recursos únicos registrados en auditoría."""
    rows = db.query(Auditoria.recurso).distinct().order_by(Auditoria.recurso).all()
    return [r[0] for r in rows if r[0]]


def generate_audit_csv(records: List[Auditoria]) -> str:
    """Genera una exportación en formato CSV estandarizado a partir de una lista de registros."""
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "ID",
        "Fecha (UTC)",
        "Acción",
        "Usuario",
        "Usuario ID",
        "IP",
        "Recurso",
        "Recurso ID",
        "Detalle",
        "Datos Previos",
        "Datos Nuevos"
    ])

    for r in records:
        writer.writerow([
            r.id,
            r.fecha.isoformat() if r.fecha else "",
            r.accion,
            r.usuario,
            r.usuario_id or "",
            r.ip_address or "",
            r.recurso or "",
            r.recurso_id or "",
            r.detalle or "",
            r.datos_previos or "",
            r.datos_nuevos or ""
        ])

    return output.getvalue()
