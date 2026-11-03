from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import require_roles
from backend.app.models.pedido import Pedido
from backend.app.models.usuario import Usuario
from backend.app.schemas.schemas import (
    AsignarRepartidorRequest,
    EntregaDeliveryRequest,
    EstadoDeliveryRequest,
    PedidoBaseOut,
    UbicacionRepartidorRequest,
)
from backend.app.websockets.manager import ws_manager

router = APIRouter(prefix="/delivery", tags=["Delivery y repartidores"])


@router.get("/despacho/pedidos", response_model=List[PedidoBaseOut])
def listar_pedidos_despacho(
    db: Session = Depends(get_db),
    user=Depends(require_roles(["admin", "supervisor", "caja"])),
):
    return (
        db.query(Pedido)
        .filter(
            Pedido.tipo == "delivery",
            Pedido.estado.notin_(["CANCELADO", "ENTREGADO"]),
            Pedido.estado_pago != "PENDIENTE_VALIDACION",
        )
        .order_by(Pedido.fecha_creacion.asc())
        .all()
    )


@router.get("/despacho/repartidores")
def listar_repartidores(
    db: Session = Depends(get_db),
    user=Depends(require_roles(["admin", "supervisor", "caja"])),
):
    couriers = (
        db.query(Usuario)
        .filter(Usuario.rol == "repartidor", Usuario.activo == True)
        .order_by(Usuario.nombre.asc())
        .all()
    )
    return [
        {"id": courier.id, "nombre": f"{courier.nombre} {courier.apellido}", "telefono": courier.telefono}
        for courier in couriers
    ]


@router.post("/despacho/pedidos/{pedido_id}/asignar")
async def asignar_repartidor(
    pedido_id: int,
    data: AsignarRepartidorRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles(["admin", "supervisor", "caja"])),
):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
    if not pedido or pedido.tipo != "delivery":
        raise HTTPException(status_code=404, detail="Pedido delivery no encontrado.")
    if pedido.estado in ["CANCELADO", "ENTREGADO"] or pedido.estado_pago != "PAGADO":
        raise HTTPException(status_code=409, detail="El pedido debe estar activo y pagado antes de asignar el reparto.")
    repartidor = (
        db.query(Usuario)
        .filter(
            Usuario.id == data.repartidor_id,
            Usuario.rol == "repartidor",
            Usuario.activo == True,
        )
        .first()
    )
    if not repartidor:
        raise HTTPException(status_code=404, detail="El repartidor no existe o está inactivo.")

    pedido.repartidor_id = repartidor.id
    pedido.estado_delivery = "ASIGNADO"
    pedido.repartidor_lat = None
    pedido.repartidor_lng = None
    pedido.ubicacion_repartidor_actualizada_at = None
    db.commit()
    await ws_manager.broadcast("DELIVERY_ACTUALIZADO", {
        "pedido_id": pedido.id,
        "repartidor_id": repartidor.id,
        "estado_delivery": pedido.estado_delivery,
    })
    return {"pedido_id": pedido.id, "repartidor_id": repartidor.id, "estado_delivery": pedido.estado_delivery}


@router.get("/mis-pedidos", response_model=List[PedidoBaseOut])
def listar_mis_pedidos(
    db: Session = Depends(get_db),
    user=Depends(require_roles(["repartidor"])),
):
    return (
        db.query(Pedido)
        .filter(
            Pedido.repartidor_id == user.id,
            Pedido.tipo == "delivery",
            Pedido.estado_delivery != "ENTREGADO",
            Pedido.estado != "CANCELADO",
        )
        .order_by(Pedido.fecha_creacion.asc())
        .all()
    )


@router.post("/pedidos/{pedido_id}/estado")
async def actualizar_estado_delivery(
    pedido_id: int,
    data: EstadoDeliveryRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles(["repartidor"])),
):
    pedido = db.query(Pedido).filter(
        Pedido.id == pedido_id,
        Pedido.repartidor_id == user.id,
        Pedido.tipo == "delivery",
    ).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="El pedido no está asignado a este repartidor.")

    now = datetime.now(timezone.utc)
    if data.estado == "RECOGIDO":
        if pedido.estado_delivery != "ASIGNADO" or pedido.estado != "LISTO":
            raise HTTPException(status_code=409, detail="Solo se puede recoger un pedido asignado que cocina marcó como listo.")
        pedido.estado_delivery = "RECOGIDO"
        pedido.fecha_retiro = now
    elif data.estado == "EN_CAMINO":
        if pedido.estado_delivery != "RECOGIDO":
            raise HTTPException(status_code=409, detail="Primero debes confirmar la recogida del pedido.")
        pedido.estado_delivery = "EN_CAMINO"
        pedido.fecha_en_camino = now

    db.commit()
    await ws_manager.broadcast("DELIVERY_ACTUALIZADO", {
        "pedido_id": pedido.id,
        "repartidor_id": user.id,
        "estado_delivery": pedido.estado_delivery,
    })
    return {"pedido_id": pedido.id, "estado_delivery": pedido.estado_delivery}


@router.post("/pedidos/{pedido_id}/ubicacion")
def actualizar_ubicacion_repartidor(
    pedido_id: int,
    data: UbicacionRepartidorRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles(["repartidor"])),
):
    pedido = db.query(Pedido).filter(
        Pedido.id == pedido_id,
        Pedido.repartidor_id == user.id,
        Pedido.tipo == "delivery",
    ).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="El pedido no está asignado a este repartidor.")
    if pedido.estado_delivery != "EN_CAMINO":
        raise HTTPException(status_code=409, detail="Solo se comparte la ubicación durante una entrega en camino.")

    pedido.repartidor_lat = data.lat
    pedido.repartidor_lng = data.lng
    pedido.ubicacion_repartidor_actualizada_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "pedido_id": pedido.id,
        "ubicacion_actualizada_at": pedido.ubicacion_repartidor_actualizada_at,
    }


@router.post("/pedidos/{pedido_id}/entregar")
async def confirmar_entrega_delivery(
    pedido_id: int,
    data: EntregaDeliveryRequest,
    db: Session = Depends(get_db),
    user=Depends(require_roles(["repartidor"])),
):
    pedido = db.query(Pedido).filter(
        Pedido.id == pedido_id,
        Pedido.repartidor_id == user.id,
        Pedido.tipo == "delivery",
    ).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="El pedido no está asignado a este repartidor.")
    if pedido.estado_delivery != "EN_CAMINO":
        raise HTTPException(status_code=409, detail="El pedido debe estar en camino para confirmar la entrega.")
    if not pedido.codigo_otp or pedido.codigo_otp != data.codigo_otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Código de entrega incorrecto.")

    pedido.estado_delivery = "ENTREGADO"
    pedido.estado = "ENTREGADO"
    pedido.otp_verificado = True
    pedido.fecha_entrega = datetime.now(timezone.utc)
    pedido.repartidor_lat = None
    pedido.repartidor_lng = None
    pedido.ubicacion_repartidor_actualizada_at = None
    db.commit()
    await ws_manager.broadcast("CAMBIO_ESTADO_PEDIDO", {
        "pedido_id": pedido.id,
        "nuevo_estado": "ENTREGADO",
        "estado_delivery": pedido.estado_delivery,
        "numero_mesa": pedido.numero_mesa,
    })
    return {"pedido_id": pedido.id, "estado_delivery": pedido.estado_delivery}
