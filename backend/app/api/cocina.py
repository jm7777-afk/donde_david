from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import require_roles
from backend.app.models.pedido import Pedido
from backend.app.models.detalle_pedido import DetallePedido
from backend.app.models.producto import Producto
from backend.app.models.mesa import Mesa
from backend.app.models.movimiento_inventario import MovimientoInventario
from backend.app.schemas.schemas import PedidoOut
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
        Pedido.estado.in_(["PENDIENTE", "COBRADO", "EN_PREPARACION", "LISTO"])
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

    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if estado == "CANCELADO":
        if pedido.estado in ["CANCELADO", "ENTREGADO", "COBRADO"] or pedido.estado_pago == "PAGADO":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El pedido ya no puede cancelarse en su estado actual."
            )
        for detalle in pedido.detalles:
            producto = db.query(Producto).filter(
                Producto.id == detalle.producto_id
            ).with_for_update().first()
            if not producto:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"No se pudo restaurar inventario del producto #{detalle.producto_id}."
                )
            stock_before = int(producto.stock or 0)
            producto.stock = stock_before + detalle.cantidad
            db.add(MovimientoInventario(
                producto_id=producto.id,
                tipo_movimiento="DEVOLUCION",
                cantidad_cambio=detalle.cantidad,
                cantidad_anterior=stock_before,
                cantidad_nueva=producto.stock,
                motivo=f"Cancelación de pedido #{pedido.id}",
                usuario_id=user.id
            ))
        if pedido.tipo == "mesa":
            try:
                mesa_numero = int(pedido.numero_mesa.lower().replace("mesa", "").strip())
            except ValueError:
                mesa_numero = None
            if mesa_numero is not None:
                mesa = db.query(Mesa).filter(Mesa.numero_mesa == mesa_numero).with_for_update().first()
                other_open_order = db.query(Pedido.id).filter(
                    Pedido.tipo == "mesa",
                    Pedido.numero_mesa == pedido.numero_mesa,
                    Pedido.id != pedido.id,
                    Pedido.estado.notin_(["CANCELADO", "COBRADO", "ENTREGADO"]),
                ).first()
                if mesa and not other_open_order:
                    mesa.estado = "LIBRE"
                    mesa.cliente_actual = None
        pedido.estado_pago = "CANCELADO"

    pedido.estado = estado
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
    detalle = db.query(DetallePedido).filter(DetallePedido.id == detalle_id).first()
    if not detalle:
        raise HTTPException(status_code=404, detail="Item de pedido no encontrado")

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
