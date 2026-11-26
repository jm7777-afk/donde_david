from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import require_roles
from backend.app.models.pedido import Pedido
from backend.app.models.detalle_pedido import DetallePedido
from backend.app.schemas.schemas import PedidoOut
from backend.app.services.orders import restore_order_stock
from backend.app.services.tables import parse_table_number, refresh_table_state
from backend.app.websockets.manager import ws_manager

router = APIRouter(prefix="/cocina", tags=["Cocina / KDS"])

@router.get("/pedidos", response_model=List[PedidoOut])
def get_pedidos_cocina(
    tipo: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor", "cocina", "caja", "mesero"]))
):
    if tipo is not None and tipo not in {"mesa", "llevar", "delivery"}:
        raise HTTPException(status_code=422, detail="Modalidad de pedido inválida.")
    # Retrieve active orders for kitchen (PENDIENTE, COBRADO, EN_PREPARACION, LISTO)
    query = db.query(Pedido).filter(
        Pedido.estado.in_(["PENDIENTE", "COBRADO", "EN_PREPARACION", "LISTO"]),
        or_(
            Pedido.estado_pago == "PAGADO",
            and_(Pedido.tipo == "mesa", Pedido.modo_pago == "PAGAR_DESPUES"),
        ),
    )
    if tipo:
        query = query.filter(Pedido.tipo == tipo)
    return query.order_by(Pedido.fecha_creacion.asc()).all()

@router.put("/pedidos/{pedido_id}/estado")
async def actualizar_estado_pedido(
    pedido_id: int, 
    estado: str, 
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor", "cocina", "caja", "mesero"]))
):
    valid_estados = ["PENDIENTE", "COBRADO", "EN_PREPARACION", "LISTO", "ENTREGADO", "CANCELADO"]
    if estado not in valid_estados:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Opciones: {valid_estados}")

    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if pedido.estado in ("CANCELADO", "ENTREGADO") and estado != pedido.estado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El pedido #{pedido.id} ya está en estado terminal {pedido.estado}."
        )

    if pedido.estado == "PAGO_PENDIENTE" and estado in ("EN_PREPARACION", "LISTO", "ENTREGADO"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El pedido está pendiente de validación de pago en caja."
        )

    if estado == "CANCELADO":
        if pedido.estado in ["CANCELADO", "ENTREGADO", "COBRADO"] or pedido.estado_pago == "PAGADO":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El pedido ya no puede cancelarse en su estado actual."
            )
        restore_order_stock(
            db,
            pedido,
            motivo=f"Cancelación de pedido #{pedido.id}",
            usuario_id=user.id,
            strict=True,
        )
        pedido.estado_pago = "CANCELADO"

    pedido.estado = estado
    if pedido.tipo == "mesa" and estado in {"CANCELADO", "ENTREGADO"}:
        try:
            refresh_table_state(db, parse_table_number(pedido.numero_mesa))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    if estado == "ENTREGADO" or estado == "LISTO":
        pedido.fecha_entrega = datetime.now(timezone.utc)
    
    # Update individual items state if marking entire order
    for detalle in pedido.detalles:
        if (estado == "EN_PREPARACION" or estado == "COBRADO") and detalle.estado in ["PENDIENTE", "COBRADO"]:
            detalle.estado = "EN_PREPARACION"
        elif estado == "LISTO":
            detalle.estado = "LISTO"
            detalle.fecha_listo = datetime.now(timezone.utc)

    if pedido.tipo == "llevar" and estado == "LISTO":
        pedido.estado_retiro = "LISTO_PARA_RETIRAR"

    db.commit()

    # Broadcast event
    await ws_manager.broadcast("CAMBIO_ESTADO_PEDIDO", {
        "pedido_id": pedido.id,
        "numero_mesa": pedido.numero_mesa,
        "nuevo_estado": estado
    })

    return {"mensaje": "Estado actualizado exitosamente", "pedido_id": pedido_id, "estado": estado}

@router.put("/detalles/{detalle_id}/estado")
async def actualizar_estado_detalle(
    detalle_id: int, 
    estado: str, 
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor", "cocina", "caja", "mesero"]))
):
    valid_item_estados = ["PENDIENTE", "EN_PREPARACION", "LISTO"]
    if estado not in valid_item_estados:
        raise HTTPException(
            status_code=400,
            detail=f"Estado de ítem inválido. Opciones: {valid_item_estados}"
        )

    detalle = db.query(DetallePedido).filter(DetallePedido.id == detalle_id).with_for_update().first()
    if not detalle:
        raise HTTPException(status_code=404, detail="Item de pedido no encontrado")

    pedido = db.query(Pedido).filter(Pedido.id == detalle.pedido_id).with_for_update().first()
    if pedido and pedido.estado in ("CANCELADO", "ENTREGADO", "PAGO_PENDIENTE"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pueden modificar ítems de un pedido en estado {pedido.estado}."
        )

    detalle.estado = estado
    if estado == "LISTO":
        detalle.fecha_listo = datetime.now(timezone.utc)

    db.commit()

    # Check if all items in the parent order are ready
    pedido = db.query(Pedido).filter(Pedido.id == detalle.pedido_id).first()
    todos_listos = all(d.estado == "LISTO" for d in pedido.detalles)
    if todos_listos and pedido.estado != "LISTO":
        pedido.estado = "LISTO"
        pedido.fecha_entrega = datetime.now(timezone.utc)
        if pedido.tipo == "llevar":
            pedido.estado_retiro = "LISTO_PARA_RETIRAR"
        db.commit()
        await ws_manager.broadcast("CAMBIO_ESTADO_PEDIDO", {
            "pedido_id": pedido.id,
            "numero_mesa": pedido.numero_mesa,
            "nuevo_estado": "LISTO",
            "estado_retiro": pedido.estado_retiro,
        })

    return {"mensaje": "Estado del ítem actualizado", "detalle_id": detalle_id, "estado": estado}
