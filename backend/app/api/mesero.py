from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import require_roles
from backend.app.models.pedido import Pedido
from backend.app.models.mesa import Mesa
from backend.app.models.solicitud_mesa import SolicitudMesa
from backend.app.schemas.schemas import PedidoOut, CambiarMesaRequest, SolicitudMesaEstado, MesaLimpiezaRequest
from backend.app.services.tables import has_active_table_orders, parse_table_number, refresh_table_state
from backend.app.websockets.manager import ws_manager

router = APIRouter(prefix="/mesero", tags=["Panel de Meseros"])

@router.get("/mesas")
def get_mesas_mesero(
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor", "mesero", "caja"]))
):
    mesas = db.query(Mesa).order_by(Mesa.numero_mesa.asc()).all()
    active_orders = db.query(Pedido).filter(
        Pedido.tipo == "mesa",
        or_(
            Pedido.estado.in_(["PENDIENTE", "COBRADO", "EN_PREPARACION", "LISTO"]),
            and_(Pedido.estado == "ENTREGADO", Pedido.estado_pago != "PAGADO"),
        ),
    ).all()
    pending_requests = db.query(SolicitudMesa).filter(SolicitudMesa.estado == "PENDIENTE").all()
    orders_by_table = {}
    for order in active_orders:
        try:
            number = int(order.numero_mesa.lower().replace("mesa", "").strip())
        except (ValueError, AttributeError):
            continue
        orders_by_table.setdefault(number, []).append(order)

    now = datetime.now(timezone.utc)
    summaries = []
    for mesa in mesas:
        orders = orders_by_table.get(mesa.numero_mesa, [])
        first_order = min(orders, key=lambda order: order.fecha_creacion or now) if orders else None
        created = first_order.fecha_creacion if first_order else None
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        summaries.append({
            "id": mesa.id,
            "numero_mesa": mesa.numero_mesa,
            "estado": mesa.estado,
            "codigo_qr": mesa.codigo_qr,
            "capacidad": mesa.capacidad,
            "cliente_actual": mesa.cliente_actual,
            "tiempo_ocupacion_min": max(0, int((now - created).total_seconds() // 60)) if created else 0,
            "pedidos_activos": len(orders),
            "solicitudes_pendientes": sum(1 for item in pending_requests if item.mesa_id == mesa.id),
        })
    return summaries


@router.put("/mesas/{mesa_id}/limpieza")
async def actualizar_limpieza_mesa(
    mesa_id: int,
    data: MesaLimpiezaRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles(["admin", "supervisor", "mesero", "caja"])),
):
    mesa = db.query(Mesa).filter(Mesa.id == mesa_id).with_for_update().first()
    if not mesa:
        raise HTTPException(status_code=404, detail="Mesa no encontrada.")

    if has_active_table_orders(db, mesa.numero_mesa):
        raise HTTPException(status_code=409, detail="La mesa todavía tiene pedidos activos.")

    if data.accion == "INICIAR":
        if mesa.estado != "PENDIENTE_LIMPIEZA":
            raise HTTPException(status_code=409, detail="La mesa no está pendiente de limpieza.")
        mesa.estado = "EN_LIMPIEZA"
    else:
        if mesa.estado != "EN_LIMPIEZA":
            raise HTTPException(status_code=409, detail="La mesa debe estar en limpieza para liberarla.")
        mesa.estado = "LIBRE"
        mesa.cliente_actual = None
        mesa.pedido_activo_id = None
        mesa.subtotal_acumulado = 0.0
    mesa.fecha_actualizacion = datetime.now(timezone.utc)
    db.commit()

    await ws_manager.broadcast("MESA_ACTUALIZADA", {
        "mesa_id": mesa.id,
        "numero_mesa": mesa.numero_mesa,
        "estado": mesa.estado,
        "actualizado_por": user.nombre,
    })
    return {"mesa_id": mesa.id, "numero_mesa": mesa.numero_mesa, "estado": mesa.estado}


@router.get("/solicitudes")
def get_solicitudes_mesa(
    db: Session = Depends(get_db),
    user=Depends(require_roles(["admin", "supervisor", "mesero", "caja"])),
):
    requests = (
        db.query(SolicitudMesa, Mesa.numero_mesa)
        .join(Mesa, Mesa.id == SolicitudMesa.mesa_id)
        .filter(SolicitudMesa.estado == "PENDIENTE")
        .order_by(SolicitudMesa.fecha_creacion.asc())
        .all()
    )
    return [
        {
            "id": item.id,
            "mesa": table_number,
            "pedido_id": item.pedido_id,
            "tipo": item.tipo,
            "nota": item.nota,
            "fecha_creacion": item.fecha_creacion,
        }
        for item, table_number in requests
    ]


@router.put("/solicitudes/{solicitud_id}/estado")
async def actualizar_solicitud_mesa(
    solicitud_id: int,
    data: SolicitudMesaEstado,
    db: Session = Depends(get_db),
    user=Depends(require_roles(["admin", "supervisor", "mesero", "caja"])),
):
    solicitud = (
        db.query(SolicitudMesa)
        .filter(SolicitudMesa.id == solicitud_id)
        .with_for_update()
        .first()
    )
    if not solicitud:
        raise HTTPException(status_code=404, detail="Solicitud de mesa no encontrada.")
    if solicitud.estado != "PENDIENTE":
        raise HTTPException(status_code=409, detail="La solicitud ya fue atendida o cancelada.")

    solicitud.estado = data.estado
    if data.estado == "ATENDIDA":
        solicitud.atendido_por_id = user.id
        solicitud.fecha_atencion = datetime.now(timezone.utc)
    db.commit()
    await ws_manager.broadcast("SOLICITUD_MESA_ACTUALIZADA", {
        "id": solicitud.id,
        "mesa_id": solicitud.mesa_id,
        "estado": solicitud.estado,
        "atendido_por": user.nombre,
    })
    return {"id": solicitud.id, "estado": solicitud.estado}

@router.get("/pedidos-activos", response_model=List[PedidoOut])
def get_pedidos_activos_mesero(
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor", "mesero", "caja"]))
):
    return db.query(Pedido).filter(
        Pedido.tipo == "mesa",
        Pedido.estado.in_(["PENDIENTE", "COBRADO", "EN_PREPARACION", "LISTO"])
    ).order_by(Pedido.fecha_creacion.asc()).all()

@router.post("/pedidos/{pedido_id}/cambiar-mesa")
async def cambiar_mesa_pedido(
    pedido_id: int,
    data: CambiarMesaRequest,
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor", "mesero", "caja"]))
):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if pedido.tipo != "mesa" or pedido.estado in {"CANCELADO", "ENTREGADO"}:
        raise HTTPException(status_code=409, detail="Solo se pueden reasignar pedidos activos en mesa.")

    nueva_mesa_num = data.nueva_mesa
    nueva_mesa_obj = db.query(Mesa).filter(Mesa.numero_mesa == nueva_mesa_num).with_for_update().first()
    if not nueva_mesa_obj:
        raise HTTPException(status_code=404, detail=f"La Mesa #{nueva_mesa_num} no existe")
    try:
        mesa_anterior_num = parse_table_number(pedido.numero_mesa)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="El pedido tiene una mesa inválida y no puede reasignarse.") from exc
    if nueva_mesa_num == mesa_anterior_num:
        raise HTTPException(status_code=409, detail="El pedido ya está asignado a esa mesa.")
    if nueva_mesa_obj.estado != "LIBRE":
        raise HTTPException(status_code=409, detail="La nueva mesa no está disponible.")

    mesa_anterior_str = pedido.numero_mesa
    nueva_mesa_obj.estado = "OCUPADA"
    nueva_mesa_obj.cliente_actual = pedido.nombre_factura or f"Cliente Pedido #{pedido.id}"
    pedido.numero_mesa = f"Mesa {nueva_mesa_num}"
    refresh_table_state(db, mesa_anterior_num)
    db.commit()
    db.refresh(pedido)

    await ws_manager.broadcast("CAMBIO_ESTADO_PEDIDO", {
        "pedido_id": pedido.id,
        "nuevo_estado": pedido.estado,
        "numero_mesa": pedido.numero_mesa,
        "accion": "CAMBIO_MESA",
        "mesero": user.nombre
    })

    return {
        "mensaje": f"Pedido #{pedido.id} reasignado exitosamente de {mesa_anterior_str} a Mesa #{nueva_mesa_num}",
        "pedido_id": pedido.id,
        "nueva_mesa": f"Mesa {nueva_mesa_num}"
    }

@router.post("/pedidos/{pedido_id}/marcar-entregado")
async def marcar_pedido_entregado(
    pedido_id: int, 
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor", "mesero", "caja"]))
):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if pedido.tipo != "mesa" or pedido.estado != "LISTO":
        raise HTTPException(status_code=409, detail="Solo se pueden entregar pedidos de mesa que estén listos.")

    pedido.estado = "ENTREGADO"
    if pedido.tipo == "mesa":
        try:
            refresh_table_state(db, parse_table_number(pedido.numero_mesa))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()

    await ws_manager.broadcast("CAMBIO_ESTADO_PEDIDO", {
        "pedido_id": pedido.id,
        "nuevo_estado": "ENTREGADO",
        "numero_mesa": pedido.numero_mesa,
        "mesero": user.nombre
    })

    return {"mensaje": f"Pedido #{pedido.id} marcado como ENTREGADO por el mesero {user.nombre}."}
