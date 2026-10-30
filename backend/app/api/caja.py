from typing import List, Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hmac
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from backend.app.core.database import get_db
from backend.app.core.security import require_roles
from backend.app.models.pedido import Pedido
from backend.app.models.detalle_pedido import DetallePedido
from backend.app.models.producto import Producto
from backend.app.models.turno import Turno
from backend.app.models.configuracion import Configuracion
from backend.app.models.mesa import Mesa
from backend.app.models.usuario import Usuario
from backend.app.models.movimiento_inventario import MovimientoInventario
from backend.app.models.movimiento_caja import MovimientoCaja
from backend.app.models.arqueo_turno import ArqueoTurno
from backend.app.schemas.schemas import PedidoOut, TurnoApertura, TurnoCierre, TurnoOut, CobrarPedidoRequest, DetallePedidoItem, MovimientoCajaCreate, MovimientoCajaOut, ConfirmarRetiroRequest
from backend.app.schemas.schemas import ConfirmarPagoRequest
from backend.app.services.exchange_rate import get_bcv_rate
from backend.app.websockets.manager import ws_manager

router = APIRouter(
    prefix="/caja",
    tags=["Caja / Control de Turnos"],
    dependencies=[Depends(require_roles(["admin", "supervisor", "caja"]))]
)

class PedidoRapidoPOSCreate(BaseModel):
    numero_mesa: str # e.g. "Mesa 5", "Mostrador"
    tipo: Optional[str] = "llevar"
    metodo_pago: str = Field(min_length=1, max_length=50)
    monto_recibido: float = Field(ge=0, allow_inf_nan=False)
    nit_cliente: Optional[str] = "CF"
    nombre_factura: Optional[str] = "Consumidor Final"
    detalles: List[DetallePedidoItem] = Field(min_length=1, max_length=50)


PAYMENT_METHODS = ("Efectivo", "Pago Móvil", "Punto de Venta")


def _normalize_payment_method(method: Optional[str]) -> Optional[str]:
    normalized = (method or "").strip().casefold()
    if normalized in {"efectivo", "cash"}:
        return "Efectivo"
    if normalized in {"pago móvil", "pago movil", "mobile payment"}:
        return "Pago Móvil"
    if normalized in {"punto de venta", "tarjeta", "card", "pos"}:
        return "Punto de Venta"
    return None


def _expected_shift_totals(db: Session, turno: Turno) -> dict[str, float]:
    totals = {method: Decimal("0.00") for method in PAYMENT_METHODS}
    totals["Efectivo"] += Decimal(str(turno.monto_apertura or 0))
    orders = db.query(Pedido.metodo_pago, Pedido.total).filter(
        Pedido.turno_id == turno.id,
        Pedido.estado_pago == "PAGADO",
    ).all()
    for payment_method, amount in orders:
        normalized = _normalize_payment_method(payment_method)
        if normalized:
            totals[normalized] += Decimal(str(amount or 0))
    expenses = db.query(MovimientoCaja).filter(
        MovimientoCaja.turno_id == turno.id,
        MovimientoCaja.tipo == "EGRESO",
    ).all()
    for movement in expenses:
        normalized = _normalize_payment_method(movement.metodo_pago)
        if normalized:
            totals[normalized] -= Decimal(str(movement.monto_usd or 0))
    return {
        method: round(float(amount), 2)
        for method, amount in totals.items()
    }


@router.get("/turno-activo", response_model=TurnoOut)
def get_turno_activo(
    db: Session = Depends(get_db)
):
    turno = db.query(Turno).filter(Turno.activo == True).order_by(Turno.id.desc()).first()
    if not turno:
        raise HTTPException(status_code=404, detail="No hay ningún turno de caja activo.")
    expected_totals = _expected_shift_totals(db, turno)
    turno.efectivo_esperado = expected_totals["Efectivo"]
    turno.esperado_por_metodo = expected_totals
    return turno


@router.get("/movimientos", response_model=List[MovimientoCajaOut])
def get_movimientos_caja(db: Session = Depends(get_db)):
    turno = db.query(Turno).filter(Turno.activo == True).order_by(Turno.id.desc()).first()
    if not turno:
        raise HTTPException(status_code=404, detail="No hay turno activo para consultar movimientos.")
    return db.query(MovimientoCaja).filter(
        MovimientoCaja.turno_id == turno.id
    ).order_by(MovimientoCaja.fecha.desc()).all()


@router.post("/movimientos", response_model=MovimientoCajaOut, status_code=status.HTTP_201_CREATED)
async def registrar_movimiento_caja(
    data: MovimientoCajaCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor", "caja"])),
):
    turno = db.query(Turno).filter(Turno.activo == True).order_by(Turno.id.desc()).first()
    if not turno:
        raise HTTPException(status_code=409, detail="Debe abrir un turno antes de registrar un egreso.")
    movimiento = MovimientoCaja(
        turno_id=turno.id,
        usuario_id=current_user.id,
        tipo="EGRESO",
        metodo_pago=data.metodo_pago,
        monto_usd=round(data.monto_usd, 2),
        concepto=data.concepto.strip(),
        observacion=data.observacion.strip() if data.observacion else None,
    )
    db.add(movimiento)
    db.commit()
    db.refresh(movimiento)
    await ws_manager.broadcast("MOVIMIENTO_CAJA", {
        "turno_id": turno.id,
        "tipo": movimiento.tipo,
        "monto_usd": float(movimiento.monto_usd),
        "metodo_pago": movimiento.metodo_pago,
    })
    return movimiento

@router.post("/abrir-turno", response_model=TurnoOut)
async def abrir_turno(
    data: TurnoApertura,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "supervisor", "caja"]))
):
    turno_existente = db.query(Turno).filter(Turno.activo == True).first()
    if turno_existente:
        raise HTTPException(status_code=400, detail=f"Ya existe un turno activo (# {turno_existente.numero_turno}).")

    ultimo_turno = db.query(Turno).order_by(Turno.numero_turno.desc()).first()
    nuevo_num = (ultimo_turno.numero_turno + 1) if ultimo_turno else 1

    nuevo_turno = Turno(
        numero_turno=nuevo_num,
        monto_apertura=data.monto_apertura,
        total_ventas=0.0,
        total_pedidos=0,
        activo=True,
        usuario_caja_id=current_user.id
    )
    db.add(nuevo_turno)
    db.commit()
    db.refresh(nuevo_turno)

    await ws_manager.broadcast("TURNO_ACTUALIZADO", {
        "accion": "ABIERTO",
        "turno_id": nuevo_turno.id,
        "numero_turno": nuevo_turno.numero_turno,
        "usuario": current_user.nombre
    })

    return nuevo_turno

@router.post("/cerrar-turno", response_model=TurnoOut)
async def cerrar_turno(
    data: TurnoCierre,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "supervisor", "caja"]))
):
    turno = db.query(Turno).filter(Turno.activo == True).order_by(Turno.id.desc()).first()
    if not turno:
        raise HTTPException(status_code=404, detail="No hay turno activo para cerrar.")

    expected_totals = _expected_shift_totals(db, turno)
    expected_total = expected_totals["Efectivo"]
    if data.arqueo is not None:
        supplied_methods = [item.metodo_pago for item in data.arqueo]
        if len(set(supplied_methods)) != len(PAYMENT_METHODS) or set(supplied_methods) != set(PAYMENT_METHODS):
            raise HTTPException(status_code=422, detail="El arqueo debe incluir exactamente efectivo, pago móvil y punto de venta.")
        declared_cash = next(item.contado_usd for item in data.arqueo if item.metodo_pago == "Efectivo")
        if round(declared_cash, 2) != round(data.monto_cierre, 2):
            raise HTTPException(status_code=422, detail="El monto de cierre debe coincidir con el efectivo contado.")
        turno.arqueo.clear()
        for item in data.arqueo:
            expected = expected_totals[item.metodo_pago]
            counted = round(item.contado_usd, 2)
            turno.arqueo.append(ArqueoTurno(
                metodo_pago=item.metodo_pago,
                esperado_usd=expected,
                contado_usd=counted,
                diferencia_usd=round(counted - expected, 2),
            ))
    turno.fecha_cierre = datetime.now(timezone.utc)
    turno.monto_cierre = data.monto_cierre
    turno.efectivo_declarado = data.monto_cierre
    turno.diferencia = round(float(data.monto_cierre) - expected_total, 2)
    turno.efectivo_esperado = expected_total
    turno.activo = False

    db.commit()
    db.refresh(turno)

    await ws_manager.broadcast("TURNO_ACTUALIZADO", {
        "accion": "CERRADO",
        "turno_id": turno.id,
        "numero_turno": turno.numero_turno,
        "total_ventas": float(turno.total_ventas or 0.0),
        "usuario": current_user.nombre
    })

    return turno


@router.get("/productos-frecuentes")
def get_productos_frecuentes(
    db: Session = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        db.query(
            Producto.id,
            Producto.nombre,
            Producto.precio,
            Producto.precio_promocion,
            func.sum(DetallePedido.cantidad).label("unidades_vendidas"),
        )
        .join(DetallePedido, DetallePedido.producto_id == Producto.id)
        .join(Pedido, Pedido.id == DetallePedido.pedido_id)
        .filter(
            Producto.activo == True,
            Producto.disponible == True,
            Producto.stock > 0,
            Pedido.estado_pago == "PAGADO",
            func.coalesce(Pedido.fecha_pago, Pedido.fecha_creacion) >= since,
        )
        .group_by(Producto.id, Producto.nombre, Producto.precio, Producto.precio_promocion)
        .order_by(func.sum(DetallePedido.cantidad).desc(), Producto.nombre.asc())
        .limit(8)
        .all()
    )
    return [
        {
            "id": row.id,
            "nombre": row.nombre,
            "precio": float(row.precio or 0),
            "precio_promocion": float(row.precio_promocion) if row.precio_promocion is not None else None,
            "unidades_vendidas": int(row.unidades_vendidas or 0),
        }
        for row in rows
    ]

@router.get("/pedidos-pendientes", response_model=List[PedidoOut])
def get_pedidos_pendientes_cobro(
    db: Session = Depends(get_db)
):
    return db.query(Pedido).filter(
        Pedido.estado.in_(["PAGO_PENDIENTE", "PENDIENTE", "EN_PREPARACION", "LISTO"])
    ).order_by(Pedido.fecha_creacion.asc()).all()

@router.get("/pedidos-cobrados", response_model=List[PedidoOut])
def get_pedidos_cobrados(
    db: Session = Depends(get_db)
):
    turno = db.query(Turno).filter(Turno.activo == True).first()
    query = db.query(Pedido).filter(Pedido.estado.in_(["COBRADO", "ENTREGADO"]))
    if turno:
        query = query.filter(Pedido.turno_id == turno.id)
    return query.order_by(Pedido.fecha_creacion.desc()).all()


@router.get("/pedidos-retiro", response_model=List[PedidoOut])
def get_pedidos_retiro(db: Session = Depends(get_db)):
    return db.query(Pedido).filter(
        Pedido.tipo == "llevar",
        Pedido.estado_retiro == "LISTO_PARA_RETIRAR",
        Pedido.estado != "ENTREGADO",
    ).order_by(Pedido.fecha_creacion.asc()).all()


@router.post("/pedidos/{pedido_id}/confirmar-retiro")
async def confirmar_retiro_pedido(
    pedido_id: int,
    data: ConfirmarRetiroRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor", "caja"])),
):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
    if not pedido or pedido.tipo != "llevar":
        raise HTTPException(status_code=404, detail="Pedido de retiro no encontrado.")
    if pedido.estado_retiro != "LISTO_PARA_RETIRAR" or not pedido.codigo_retiro:
        raise HTTPException(status_code=409, detail="El pedido todavía no está listo para retirar.")
    if not hmac.compare_digest(pedido.codigo_retiro, data.codigo_retiro):
        raise HTTPException(status_code=422, detail="Código de retiro incorrecto.")

    now = datetime.now(timezone.utc)
    pedido.estado_retiro = "RETIRADO"
    pedido.fecha_retiro = now
    pedido.fecha_entrega = now
    pedido.estado = "ENTREGADO"
    db.commit()
    await ws_manager.broadcast("CAMBIO_ESTADO_PEDIDO", {
        "pedido_id": pedido.id,
        "numero_mesa": pedido.numero_mesa,
        "nuevo_estado": pedido.estado,
        "estado_retiro": pedido.estado_retiro,
        "usuario": current_user.nombre,
    })
    return {"pedido_id": pedido.id, "estado_retiro": pedido.estado_retiro, "mensaje": "Retiro confirmado."}


@router.post("/pedidos/{pedido_id}/confirmar-pago")
async def confirmar_pago_pedido(
    pedido_id: int,
    data: ConfirmarPagoRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "supervisor", "caja"]))
):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
    if not pedido or pedido.estado_pago != "PENDIENTE_VALIDACION":
        raise HTTPException(status_code=404, detail="No existe un pago móvil pendiente de validar para este pedido.")

    if data.aprobado:
        turno = db.query(Turno).filter(Turno.activo == True).with_for_update().first()
        if not turno:
            raise HTTPException(status_code=409, detail="Debe abrir un turno de caja antes de confirmar el pago.")
        pedido.estado_pago = "PAGADO"
        pedido.fecha_pago = datetime.now(timezone.utc)
        pedido.estado = "PENDIENTE"
        pedido.monto_recibido = pedido.monto_pago
        pedido.cambio = 0
        pedido.factura_numero = f"FAC-DD-{pedido.id:06d}"
        pedido.turno_id = turno.id
        turno.total_ventas = round(float(turno.total_ventas or 0) + float(pedido.total or 0), 2)
        turno.total_pedidos = int(turno.total_pedidos or 0) + 1
        message = "Pago Móvil validado y pedido liberado a cocina."
    else:
        pedido.estado_pago = "RECHAZADO"
        pedido.estado = "CANCELADO"
        for detalle in pedido.detalles:
            producto = db.query(Producto).filter(Producto.id == detalle.producto_id).with_for_update().first()
            if producto:
                anterior = producto.stock
                producto.stock += detalle.cantidad
                db.add(MovimientoInventario(
                    producto_id=producto.id,
                    tipo_movimiento="DEVOLUCION",
                    cantidad_cambio=detalle.cantidad,
                    cantidad_anterior=anterior,
                    cantidad_nueva=producto.stock,
                    motivo=f"Pago móvil rechazado - Pedido #{pedido.id}",
                    usuario_id=current_user.id,
                ))
        if pedido.tipo == "mesa":
            try:
                mesa_numero = int(pedido.numero_mesa.lower().replace("mesa", "").strip())
            except ValueError:
                mesa_numero = None
            if mesa_numero is not None:
                mesa = db.query(Mesa).filter(Mesa.numero_mesa == mesa_numero).with_for_update().first()
                pedidos_abiertos = db.query(Pedido.id).filter(
                    Pedido.tipo == "mesa",
                    Pedido.numero_mesa == pedido.numero_mesa,
                    Pedido.id != pedido.id,
                    Pedido.estado.notin_(["CANCELADO", "COBRADO", "ENTREGADO"]),
                ).first()
                if mesa and not pedidos_abiertos:
                    mesa.estado = "LIBRE"
                    mesa.cliente_actual = None
        message = "Pago rechazado y pedido cancelado."

    db.commit()
    await ws_manager.broadcast("PAGO_VALIDADO", {
        "pedido_id": pedido.id,
        "aprobado": data.aprobado,
        "estado": pedido.estado,
        "metodo_pago": pedido.metodo_pago,
        "observacion": data.observacion,
    })
    if data.aprobado:
        await ws_manager.broadcast("NUEVO_PEDIDO", {
            "id": pedido.id,
            "numero_mesa": pedido.numero_mesa,
            "estado": pedido.estado,
            "modo_pago": pedido.modo_pago,
            "total": float(pedido.total or 0),
            "tipo": pedido.tipo,
            "detalles_count": len(pedido.detalles),
            "fecha": str(pedido.fecha_creacion),
        })
    return {"mensaje": message, "pedido_id": pedido.id, "estado_pago": pedido.estado_pago}

# ==================== COBRO Y PEDIDO RÁPIDO EN CAJA POS ====================
@router.post("/crear-y-cobrar-rapido")
async def crear_y_cobrar_rapido(
    data: PedidoRapidoPOSCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "supervisor", "caja"]))
):
    tax_config = db.query(Configuracion).filter(Configuracion.clave == "impuesto_porcentaje").first()
    tax_rate = float(tax_config.valor) if tax_config else 16.0

    turno_activo = db.query(Turno).filter(Turno.activo == True).with_for_update().first()
    if not turno_activo:
        raise HTTPException(status_code=409, detail="Debe abrir un turno de caja antes de cobrar.")
    turno_id = turno_activo.id

    requested_quantities: dict[int, int] = {}
    for item in data.detalles:
        requested_quantities[item.producto_id] = (
            requested_quantities.get(item.producto_id, 0) + item.cantidad
        )
    products: dict[int, Producto] = {}
    stock_before: dict[int, int] = {}
    for product_id, quantity in requested_quantities.items():
        product = db.query(Producto).filter(
            Producto.id == product_id,
            Producto.activo == True,
            Producto.disponible == True,
        ).with_for_update().first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Producto #{product_id} no disponible.")
        if product.stock < quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente para el producto '{product.nombre}' (Disponible: {product.stock}, Solicitado: {quantity})."
            )
        products[product_id] = product
        stock_before[product_id] = product.stock

    subtotal_acumulado = 0.0
    detalles_db = []

    for item in data.detalles:
        producto = products[item.producto_id]
        precio_num = float(producto.precio_promocion) if (producto.precio_promocion and float(producto.precio_promocion) > 0) else float(producto.precio)
        subtotal_item = round(precio_num * item.cantidad, 2)
        subtotal_acumulado += subtotal_item

        detalle = DetallePedido(
            producto_id=producto.id,
            cantidad=item.cantidad,
            precio_unitario=precio_num,
            subtotal=subtotal_item,
            estado="PENDIENTE"
        )
        detalles_db.append(detalle)

    subtotal_final = round(subtotal_acumulado, 2)
    impuesto_monto = round(subtotal_final * (tax_rate / 100.0), 2)
    total_final = round(subtotal_final + impuesto_monto, 2)

    if data.monto_recibido < total_final:
        raise HTTPException(status_code=400, detail=f"Monto recibido (${data.monto_recibido:.2f}) insuficiente. Total: ${total_final:.2f}")

    cambio_calculado = round(data.monto_recibido - total_final, 2)
    for product_id, quantity in requested_quantities.items():
        products[product_id].stock -= quantity

    nuevo_pedido = Pedido(
        numero_mesa=data.numero_mesa or "Mostrador",
        tipo=data.tipo or "llevar",
        modo_pago="PAGAR_ANTES",
        estado="COBRADO",
        subtotal=subtotal_final,
        impuesto=impuesto_monto,
        descuento=0.0,
        total=total_final,
        metodo_pago=data.metodo_pago,
        monto_recibido=data.monto_recibido,
        cambio=cambio_calculado,
        estado_pago="PAGADO",
        moneda_pago="USD",
        monto_pago=total_final,
        fecha_pago=datetime.now(timezone.utc),
        nit_cliente=data.nit_cliente or "CF",
        nombre_factura=data.nombre_factura or "Consumidor Final",
        turno_id=turno_id,
        usuario_id=current_user.id,
        detalles=detalles_db
    )

    db.add(nuevo_pedido)
    db.flush()
    for product_id, quantity in requested_quantities.items():
        db.add(MovimientoInventario(
            producto_id=product_id,
            tipo_movimiento="VENTA",
            cantidad_cambio=-quantity,
            cantidad_anterior=stock_before[product_id],
            cantidad_nueva=products[product_id].stock,
            motivo=f"Pedido #{nuevo_pedido.id}",
            usuario_id=current_user.id
        ))
    factura_num = f"FAC-DD-{nuevo_pedido.id:06d}"
    nuevo_pedido.factura_numero = factura_num

    current_ventas = float(turno_activo.total_ventas or 0.0)
    turno_activo.total_ventas = round(current_ventas + float(total_final), 2)
    turno_activo.total_pedidos += 1
    db.commit()
    db.refresh(nuevo_pedido)

    await ws_manager.broadcast("NUEVO_PEDIDO", {
        "id": nuevo_pedido.id,
        "numero_mesa": nuevo_pedido.numero_mesa,
        "estado": nuevo_pedido.estado,
        "total": nuevo_pedido.total
    })

    return {
        "mensaje": "Pedido y cobro rápido registrado exitosamente",
        "pedido_id": nuevo_pedido.id,
        "factura_numero": factura_num,
        "total": total_final,
        "monto_recibido": data.monto_recibido,
        "cambio": cambio_calculado,
        "metodo_pago": data.metodo_pago
    }

@router.post("/pedidos/{pedido_id}/cobrar")
async def cobrar_pedido(
    pedido_id: int,
    data: CobrarPedidoRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "supervisor", "caja"]))
):
    rate_status = get_bcv_rate(db) if data.moneda_pago == "VES" else None
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    if pedido.estado_pago == "PENDIENTE_VALIDACION":
        raise HTTPException(status_code=409, detail="El pago móvil debe validarse desde la cola de pagos antes de cobrar.")
    if pedido.estado_pago == "PAGADO" or pedido.factura_numero or pedido.estado in ["COBRADO", "CANCELADO", "ENTREGADO"]:
        raise HTTPException(status_code=400, detail="El pedido ya ha sido cobrado previamente.")

    turno_activo = db.query(Turno).filter(Turno.activo == True).with_for_update().first()
    if not turno_activo:
        raise HTTPException(status_code=409, detail="Debe abrir un turno de caja antes de cobrar.")

    ped_total = float(pedido.total or 0.0)
    recibido = float(data.monto_recibido or 0.0)
    exchange_rate = rate_status["tasa_cambio_bs"] if rate_status else None
    if data.moneda_pago == "VES" and exchange_rate is None:
        raise HTTPException(status_code=503, detail="No hay una tasa BCV válida disponible para cobrar en bolívares.")
    total_exigible = round(ped_total * exchange_rate, 2) if exchange_rate else ped_total

    if recibido < total_exigible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monto recibido insuficiente. Total a pagar: {total_exigible:.2f} {data.moneda_pago}."
        )
    cambio_calculado = round(recibido - total_exigible, 2)

    factura_num = f"FAC-DD-{pedido.id:06d}"

    pedido.metodo_pago = data.metodo_pago
    pedido.estado_pago = "PAGADO"
    pedido.fecha_pago = datetime.now(timezone.utc)
    pedido.moneda_pago = data.moneda_pago
    pedido.monto_pago = total_exigible
    pedido.tasa_cambio_pago = exchange_rate
    pedido.monto_recibido = recibido
    pedido.cambio = cambio_calculado
    pedido.nit_cliente = data.nit_cliente or "CF"
    pedido.nombre_factura = data.nombre_factura or "Consumidor Final"
    pedido.factura_numero = factura_num
    pedido.estado = "COBRADO"

    if pedido.tipo == "mesa" and pedido.numero_mesa:
        try:
            mesa_num = int(pedido.numero_mesa.lower().replace("mesa", "").strip())
            mesa_obj = db.query(Mesa).filter(Mesa.numero_mesa == mesa_num).first()
            if mesa_obj:
                mesa_obj.estado = "LIBRE"
                mesa_obj.cliente_actual = None
        except Exception:
            pass

    pedido.turno_id = turno_activo.id
    current_ventas = float(turno_activo.total_ventas or 0.0)
    turno_activo.total_ventas = round(current_ventas + ped_total, 2)
    turno_activo.total_pedidos += 1

    db.commit()

    await ws_manager.broadcast("PAGO_CONFIRMADO", {
        "pedido_id": pedido.id,
        "numero_mesa": pedido.numero_mesa,
        "total": ped_total,
        "factura_numero": factura_num,
        "metodo_pago": data.metodo_pago,
        "cambio": cambio_calculado
    })

    return {
        "mensaje": "Pago procesado exitosamente",
        "pedido_id": pedido.id,
        "factura_numero": factura_num,
        "total": ped_total,
        "monto_recibido": recibido,
        "cambio": cambio_calculado,
        "metodo_pago": data.metodo_pago,
        "moneda_pago": pedido.moneda_pago,
        "monto_pago": float(pedido.monto_pago or 0.0),
        "tasa_cambio_pago": float(pedido.tasa_cambio_pago) if pedido.tasa_cambio_pago else None,
    }

@router.get("/pedidos/{pedido_id}/factura")
def get_factura_pedido(pedido_id: int, db: Session = Depends(get_db)):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    
    detalles_list = []
    for d in pedido.detalles:
        detalles_list.append({
            "producto": d.producto.nombre if d.producto else "Producto",
            "cantidad": d.cantidad,
            "precio_unitario": d.precio_unitario,
            "subtotal": d.subtotal
        })

    return {
        "restaurante": "Donde David - Fresh & Tasty!",
        "nit_emisor": "10928374-9",
        "factura_numero": pedido.factura_numero or f"FAC-DD-{pedido.id:06d}",
        "fecha": str(pedido.fecha_creacion),
        "nit_cliente": pedido.nit_cliente or "CF",
        "nombre_factura": pedido.nombre_factura or "Consumidor Final",
        "tipo_pedido": pedido.tipo,
        "numero_mesa": pedido.numero_mesa,
        "direccion_delivery": pedido.direccion_delivery,
        "telefono_delivery": pedido.telefono_delivery,
        "detalles": detalles_list,
        "subtotal": float(pedido.subtotal or 0.0),
        "impuesto_iva": float(pedido.impuesto or 0.0),
        "total": float(pedido.total or 0.0),
        "metodo_pago": pedido.metodo_pago or "Efectivo",
        "moneda_pago": pedido.moneda_pago or "USD",
        "monto_pago": float(pedido.monto_pago or pedido.total or 0.0),
        "tasa_cambio_pago": float(pedido.tasa_cambio_pago) if pedido.tasa_cambio_pago else None,
        "monto_recibido": float(pedido.monto_recibido or pedido.total or 0.0),
        "cambio": float(pedido.cambio or 0.0)
    }

@router.get("/clientes/buscar")
def buscar_cliente_por_id_o_nombre(q: str, db: Session = Depends(get_db)):
    """
    Permite a la cajera buscar clientes registrados por su ID (ej: CLI-0004 o 4) o Nombre/Teléfono/Email
    """
    if not q or len(q.strip()) == 0:
        return []
    
    query_str = q.strip()
    clean_id = query_str.upper().replace("CLI-", "").replace("#", "").strip()
    
    query = db.query(Usuario).filter(Usuario.rol == "cliente", Usuario.activo == True)
    
    if clean_id.isdigit():
        target_id = int(clean_id)
        results = query.filter(
            (Usuario.id == target_id) | 
            (Usuario.nombre.ilike(f"%{query_str}%")) |
            (Usuario.apellido.ilike(f"%{query_str}%")) |
            (Usuario.nombre_usuario.ilike(f"%{query_str}%")) |
            (Usuario.telefono.ilike(f"%{query_str}%"))
        ).limit(10).all()
    else:
        results = query.filter(
            (Usuario.nombre.ilike(f"%{query_str}%")) |
            (Usuario.apellido.ilike(f"%{query_str}%")) |
            (Usuario.nombre_usuario.ilike(f"%{query_str}%")) |
            (Usuario.email.ilike(f"%{query_str}%")) |
            (Usuario.telefono.ilike(f"%{query_str}%"))
        ).limit(10).all()

    return [
        {
            "id": u.id,
            "codigo_cliente": f"CLI-{u.id:04d}",
            "nombre_completo": f"{u.nombre} {u.apellido}",
            "nombre_usuario": u.nombre_usuario,
            "email": u.email,
            "telefono": u.telefono or "Sin teléfono",
            "puntos_fidelidad": u.puntos_fidelidad or 0
        }
        for u in results
    ]
