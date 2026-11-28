import json
import math
import secrets
from typing import List, Literal, Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hmac
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
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
from backend.app.schemas.schemas import (
    PedidoOut,
    TurnoApertura,
    TurnoCierre,
    TurnoOut,
    CobrarPedidoRequest,
    DetallePedidoItem,
    MovimientoCajaCreate,
    MovimientoCajaOut,
    ConfirmarRetiroRequest,
    PromocionPedidoItem,
    PagoMixtoItem,
    DividirCuentaRequest,
    ConfirmarPagoRequest,
)
from backend.app.services.audit_service import record_audit
from backend.app.services.exchange_rate import get_bcv_rate
from backend.app.services.orders import (
    get_pricing_config,
    prepare_order_items,
    deduct_order_stock,
    restore_order_stock,
    apply_promo_bundles_pricing,
    apply_coupon_discount,
    collect_stock_alerts,
)
from backend.app.services.tables import parse_table_number, refresh_table_state
from backend.app.services.loyalty import award_order_loyalty_points
from backend.app.websockets.manager import ws_manager

router = APIRouter(
    prefix="/caja",
    tags=["Caja / Control de Turnos"],
    dependencies=[Depends(require_roles(["admin", "supervisor", "caja"]))]
)

class PedidoRapidoPOSCreate(BaseModel):
    numero_mesa: str = Field(min_length=1, max_length=50)
    tipo: Literal["mesa", "llevar", "delivery"] = "llevar"
    metodo_pago: Literal["Efectivo", "Pago Móvil", "Punto de Venta"]
    monto_recibido: float = Field(ge=0, allow_inf_nan=False)
    moneda_pago: Literal["USD", "VES"] = "USD"
    cliente_id: Optional[int] = Field(default=None, gt=0)
    nit_cliente: Optional[str] = Field(default="CF", max_length=50)
    nombre_factura: Optional[str] = Field(default="Consumidor Final", max_length=100)
    nombre_cliente_delivery: Optional[str] = Field(default=None, max_length=150)
    telefono_delivery: Optional[str] = Field(default=None, max_length=50)
    direccion_delivery: Optional[str] = Field(default=None, max_length=500)
    propina: float = Field(default=0.0, ge=0, le=500, allow_inf_nan=False)
    codigo_cupon: Optional[str] = Field(default=None, max_length=50)
    pagos_mixtos: Optional[List[PagoMixtoItem]] = Field(default=None, max_length=4)
    detalles: List[DetallePedidoItem] = Field(min_length=1, max_length=50)
    promociones: List[PromocionPedidoItem] = Field(default_factory=list, max_length=20)


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
    orders = db.query(Pedido.metodo_pago, Pedido.total, Pedido.pagos_mixtos_json).filter(
        Pedido.turno_id == turno.id,
        Pedido.estado_pago == "PAGADO",
    ).all()
    for payment_method, amount, mixed_json in orders:
        if mixed_json:
            try:
                legs = json.loads(mixed_json)
            except json.JSONDecodeError:
                legs = None
            if isinstance(legs, list) and legs:
                for leg in legs:
                    norm_leg = _normalize_payment_method(leg.get("metodo_pago") if isinstance(leg, dict) else None)
                    if norm_leg:
                        totals[norm_leg] += Decimal(str(leg.get("monto_usd") or 0))
                continue
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
    turno = db.query(Turno).filter(Turno.activo == True).with_for_update().order_by(Turno.id.desc()).first()
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
    db.flush()
    record_audit(
        db=db,
        accion="CASH_EXPENSE",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="movimientos_caja",
        recurso_id=movimiento.id,
        detalle=f"Egreso {data.metodo_pago} ${movimiento.monto_usd:.2f}: {movimiento.concepto}",
        auto_commit=False,
    )
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
    turno_existente = db.query(Turno).filter(Turno.activo == True).with_for_update().first()
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
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Otro usuario abrió el turno simultáneamente; recarga la caja.") from exc
    record_audit(
        db=db,
        accion="SHIFT_OPEN",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="turnos",
        recurso_id=nuevo_turno.id,
        detalle=f"Turno #{nuevo_turno.numero_turno} abierto con ${float(nuevo_turno.monto_apertura):.2f}",
        auto_commit=False,
    )
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
    turno = db.query(Turno).filter(Turno.activo == True).order_by(Turno.id.desc()).with_for_update().first()
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

    record_audit(
        db=db,
        accion="SHIFT_CLOSE",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="turnos",
        recurso_id=turno.id,
        detalle=f"Turno #{turno.numero_turno} cerrado. Diferencia efectivo: ${turno.diferencia:.2f}",
        auto_commit=False,
    )
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
        Pedido.estado_pago != "PAGADO",
        or_(
            Pedido.estado.in_(["PAGO_PENDIENTE", "PENDIENTE", "EN_PREPARACION", "LISTO"]),
            and_(Pedido.estado == "ENTREGADO", Pedido.estado_pago != "PAGADO"),
        )
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
    if not pedido:
        raise HTTPException(status_code=404, detail="No existe un pago móvil pendiente de validar para este pedido.")

    if pedido.estado_pago == "PAGADO" and data.aprobado:
        return {
            "mensaje": "Este pago móvil ya había sido validado; no se volvió a registrar.",
            "pedido_id": pedido.id,
            "estado_pago": pedido.estado_pago,
            "repetido": True,
        }
    if pedido.estado_pago != "PENDIENTE_VALIDACION":
        raise HTTPException(status_code=409, detail="El pago ya fue rechazado o el pedido no está pendiente de validación.")

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
        award_order_loyalty_points(db, pedido)
        turno.total_ventas = round(float(turno.total_ventas or 0) + float(pedido.total or 0), 2)
        turno.total_pedidos = int(turno.total_pedidos or 0) + 1
        message = "Pago Móvil validado y pedido liberado a cocina."
    else:
        pedido.estado_pago = "RECHAZADO"
        pedido.estado = "CANCELADO"
        restore_order_stock(
            db,
            pedido,
            motivo=f"Pago móvil rechazado - Pedido #{pedido.id}",
            usuario_id=current_user.id,
        )
        if pedido.tipo == "mesa":
            try:
                refresh_table_state(db, parse_table_number(pedido.numero_mesa))
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        message = "Pago rechazado y pedido cancelado."

    audit_detail = f"Pedido #{pedido.id}: {'aprobado' if data.aprobado else 'rechazado'}"
    if data.observacion and data.observacion.strip():
        audit_detail += f" · {data.observacion.strip()}"
    record_audit(
        db=db,
        accion="Validación de Pago Móvil",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="pedidos",
        recurso_id=pedido.id,
        detalle=audit_detail[:255],
        auto_commit=False,
        normalize_action=False,
    )

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
    return {"mensaje": message, "pedido_id": pedido.id, "estado_pago": pedido.estado_pago, "repetido": False}

# ==================== COBRO Y PEDIDO RÁPIDO EN CAJA POS ====================
@router.post("/crear-y-cobrar-rapido")
async def crear_y_cobrar_rapido(
    data: PedidoRapidoPOSCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "supervisor", "caja"]))
):
    if data.metodo_pago == "Pago Móvil" and data.moneda_pago != "VES":
        raise HTTPException(status_code=422, detail="Pago Móvil debe cobrarse en bolívares.")

    pricing = get_pricing_config(db)
    tax_rate = pricing["tax_rate"]
    delivery_fee = pricing["delivery_fee"]
    package_fee = pricing["package_fee"]

    if data.tipo == "delivery" and not all([
        data.nombre_cliente_delivery and data.nombre_cliente_delivery.strip(),
        data.telefono_delivery and data.telefono_delivery.strip(),
        data.direccion_delivery and data.direccion_delivery.strip(),
    ]):
        raise HTTPException(status_code=422, detail="El delivery requiere nombre, teléfono y dirección.")
    cliente_pos = None
    if data.cliente_id is not None:
        cliente_pos = db.query(Usuario).filter(
            Usuario.id == data.cliente_id,
            Usuario.rol == "cliente",
            Usuario.activo == True,
        ).with_for_update().first()
        if not cliente_pos:
            raise HTTPException(status_code=404, detail="El cliente seleccionado no existe o está inactivo.")

    turno_activo = db.query(Turno).filter(Turno.activo == True).with_for_update().first()
    if not turno_activo:
        raise HTTPException(status_code=409, detail="Debe abrir un turno de caja antes de cobrar.")
    turno_id = turno_activo.id

    mesa = None
    numero_mesa = data.numero_mesa.strip()
    if data.tipo == "mesa":
        try:
            mesa_number = int(numero_mesa.lower().replace("mesa", "").strip())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="El número de mesa no es válido.") from exc
        mesa = db.query(Mesa).filter(Mesa.numero_mesa == mesa_number).with_for_update().first()
        if not mesa:
            raise HTTPException(status_code=404, detail=f"La Mesa #{mesa_number} no existe.")
        if mesa.estado in {"PENDIENTE_LIMPIEZA", "EN_LIMPIEZA"}:
            raise HTTPException(status_code=409, detail="La mesa debe quedar limpia antes de recibir otro pedido.")
        numero_mesa = f"Mesa {mesa_number}"
        mesa.estado = "OCUPADA"
        mesa.cliente_actual = data.nombre_factura or f"Cliente Mesa {mesa_number}"

    products, requested_quantities, stock_before, detalles_db, subtotal_final = prepare_order_items(
        db, data.detalles, always_serialize_personalizations=True
    )
    subtotal_final, descuento_promo = apply_promo_bundles_pricing(
        db, detalles_db, data.promociones
    )
    subtotal_final, descuento_promo, _ = apply_coupon_discount(
        db, detalles_db, data.codigo_cupon, descuento_promo
    )
    propina_val = round(float(data.propina or 0.0), 2)
    impuesto_monto = round(subtotal_final * (tax_rate / 100.0), 2)
    costo_extra = delivery_fee if data.tipo == "delivery" else package_fee if data.tipo == "llevar" else 0.0
    total_final = round(subtotal_final + impuesto_monto + costo_extra + propina_val, 2)

    pagos_mixtos_str = None
    metodo_pago_final = data.metodo_pago
    needs_bcv = data.moneda_pago == "VES" or any(
        leg.moneda == "VES" for leg in (data.pagos_mixtos or [])
    )
    rate_status = get_bcv_rate(db) if needs_bcv else None
    exchange_rate = rate_status["tasa_cambio_bs"] if rate_status else None
    if needs_bcv and exchange_rate is None:
        raise HTTPException(status_code=503, detail="No hay una tasa BCV válida para cobrar en bolívares.")

    total_exigible = round(total_final * exchange_rate, 2) if (data.moneda_pago == "VES" and exchange_rate) else total_final
    if data.pagos_mixtos:
        mix_sum = round(sum(float(leg.monto_usd) for leg in data.pagos_mixtos), 2)
        if abs(mix_sum - total_final) > 0.02:
            raise HTTPException(
                status_code=422,
                detail=f"La suma de pagos mixtos (${mix_sum:.2f}) debe coincidir con el total (${total_final:.2f}).",
            )
        pagos_mixtos_str = json.dumps([leg.model_dump() for leg in data.pagos_mixtos])
        metodo_pago_final = data.pagos_mixtos[0].metodo_pago if len(data.pagos_mixtos) == 1 else "Pago Mixto"
        cambio_calculado = 0.0
        monto_recibido_val = round(data.monto_recibido if data.monto_recibido >= total_exigible else total_exigible, 2)
    else:
        if data.monto_recibido < total_exigible:
            currency_mark = "Bs. " if data.moneda_pago == "VES" else "$"
            raise HTTPException(
                status_code=400,
                detail=f"Monto recibido ({currency_mark}{data.monto_recibido:.2f}) insuficiente. Total: {currency_mark}{total_exigible:.2f}",
            )
        cambio_calculado = round(data.monto_recibido - total_exigible, 2)
        monto_recibido_val = data.monto_recibido

    nuevo_pedido = Pedido(
        numero_mesa=numero_mesa if data.tipo == "mesa" else "Mostrador" if data.tipo == "llevar" else "Delivery",
        tipo=data.tipo,
        modo_pago="PAGAR_ANTES",
        estado="COBRADO",
        subtotal=subtotal_final,
        impuesto=impuesto_monto,
        costo_empaque=package_fee if data.tipo == "llevar" else 0.0,
        descuento=descuento_promo,
        propina=propina_val,
        total=total_final,
        metodo_pago=metodo_pago_final,
        pagos_mixtos_json=pagos_mixtos_str,
        monto_recibido=monto_recibido_val,
        cambio=cambio_calculado,
        estado_pago="PAGADO",
        moneda_pago=data.moneda_pago,
        monto_pago=total_exigible,
        tasa_cambio_pago=exchange_rate,
        fecha_pago=datetime.now(timezone.utc),
        nit_cliente=data.nit_cliente or "CF",
        nombre_factura=data.nombre_factura or "Consumidor Final",
        nombre_cliente_delivery=data.nombre_cliente_delivery,
        telefono_delivery=data.telefono_delivery,
        direccion_delivery=data.direccion_delivery,
        estado_delivery="PENDIENTE" if data.tipo == "delivery" else None,
        codigo_otp=f"{secrets.randbelow(900000) + 100000:06d}" if data.tipo == "delivery" else None,
        otp_verificado=False,
        codigo_retiro=f"{secrets.randbelow(900000) + 100000:06d}" if data.tipo == "llevar" else None,
        estado_retiro="PENDIENTE" if data.tipo == "llevar" else None,
        turno_id=turno_id,
        usuario_id=cliente_pos.id if cliente_pos else current_user.id,
        detalles=detalles_db
    )

    db.add(nuevo_pedido)
    db.flush()
    if data.tipo == "delivery":
        nuevo_pedido.numero_mesa = f"Delivery #{nuevo_pedido.id + 100}"
    award_order_loyalty_points(db, nuevo_pedido)
    touched_insumos = deduct_order_stock(db, nuevo_pedido.id, products, requested_quantities, stock_before, current_user.id)
    stock_alerts = collect_stock_alerts(products, touched_insumos)
    factura_num = f"FAC-DD-{nuevo_pedido.id:06d}"
    nuevo_pedido.factura_numero = factura_num

    current_ventas = float(turno_activo.total_ventas or 0.0)
    turno_activo.total_ventas = round(current_ventas + float(total_final), 2)
    turno_activo.total_pedidos += 1
    record_audit(
        db=db,
        accion="POS_QUICK_SALE",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="pedidos",
        recurso_id=nuevo_pedido.id,
        detalle=f"POS rápido {factura_num}: {metodo_pago_final} {data.moneda_pago} ${total_final:.2f}",
        auto_commit=False,
    )
    db.commit()
    db.refresh(nuevo_pedido)

    await ws_manager.broadcast("NUEVO_PEDIDO", {
        "id": nuevo_pedido.id,
        "numero_mesa": nuevo_pedido.numero_mesa,
        "estado": nuevo_pedido.estado,
        "total": nuevo_pedido.total
    })
    if stock_alerts:
        await ws_manager.broadcast("ALERTA_STOCK_CRITICO", {"pedido_id": nuevo_pedido.id, "alertas": stock_alerts})

    return {
        "mensaje": "Pedido y cobro rápido registrado exitosamente",
        "pedido_id": nuevo_pedido.id,
        "factura_numero": factura_num,
        "total": total_final,
        "propina": propina_val,
        "monto_recibido": monto_recibido_val,
        "cambio": cambio_calculado,
        "metodo_pago": metodo_pago_final,
        "moneda_pago": data.moneda_pago,
        "monto_pago": total_exigible,
        "tasa_cambio_pago": exchange_rate,
        "pagos_mixtos": data.pagos_mixtos or [],
        "codigo_retiro": nuevo_pedido.codigo_retiro,
        "codigo_otp": nuevo_pedido.codigo_otp,
    }

@router.post("/pedidos/{pedido_id}/cobrar")
async def cobrar_pedido(
    pedido_id: int,
    data: CobrarPedidoRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_roles(["admin", "supervisor", "caja"]))
):
    rate_status = None
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    if pedido.estado_pago == "PENDIENTE_VALIDACION":
        raise HTTPException(status_code=409, detail="El pago móvil debe validarse desde la cola de pagos antes de cobrar.")
    if pedido.estado_pago == "PAGADO" and pedido.factura_numero:
        same_payment = (
            pedido.metodo_pago == data.metodo_pago
            and pedido.moneda_pago == data.moneda_pago
            and round(float(pedido.monto_recibido or 0), 2) == round(float(data.monto_recibido), 2)
        )
        if same_payment:
            return {
                "mensaje": "Este pago ya estaba confirmado; no se volvió a registrar.",
                "pedido_id": pedido.id,
                "factura_numero": pedido.factura_numero,
                "total": float(pedido.total or 0),
                "monto_recibido": float(pedido.monto_recibido or 0),
                "cambio": float(pedido.cambio or 0),
                "metodo_pago": pedido.metodo_pago,
                "moneda_pago": pedido.moneda_pago,
                "monto_pago": float(pedido.monto_pago or 0),
                "tasa_cambio_pago": float(pedido.tasa_cambio_pago) if pedido.tasa_cambio_pago else None,
                "repetido": True,
            }
        raise HTTPException(status_code=409, detail="El pedido ya fue cobrado con otros datos. No se registró otro pago.")
    if pedido.factura_numero or pedido.estado == "CANCELADO":
        raise HTTPException(status_code=409, detail="El pedido no puede cobrarse en su estado actual.")

    needs_bcv = data.moneda_pago == "VES" or any(
        leg.moneda == "VES" for leg in (data.pagos_mixtos or [])
    )
    rate_status = get_bcv_rate(db) if needs_bcv else None
    turno_activo = db.query(Turno).filter(Turno.activo == True).with_for_update().first()
    if not turno_activo:
        raise HTTPException(status_code=409, detail="Debe abrir un turno de caja antes de cobrar.")

    if data.propina is not None and data.propina >= 0:
        prev_tip = float(pedido.propina or 0.0)
        new_tip = round(float(data.propina), 2)
        pedido.propina = new_tip
        pedido.total = round(float(pedido.total or 0.0) - prev_tip + new_tip, 2)

    ped_total = float(pedido.total or 0.0)
    recibido = float(data.monto_recibido or 0.0)
    exchange_rate = rate_status["tasa_cambio_bs"] if rate_status else None
    if needs_bcv and exchange_rate is None:
        raise HTTPException(status_code=503, detail="No hay una tasa BCV válida disponible para cobrar en bolívares.")
    total_exigible = round(ped_total * exchange_rate, 2) if (data.moneda_pago == "VES" and exchange_rate) else ped_total

    pagos_mixtos_str = None
    metodo_final = data.metodo_pago
    if data.pagos_mixtos:
        mix_sum = round(sum(float(leg.monto_usd) for leg in data.pagos_mixtos), 2)
        if abs(mix_sum - ped_total) > 0.02:
            raise HTTPException(
                status_code=422,
                detail=f"La suma de pagos mixtos (${mix_sum:.2f}) debe coincidir con el total (${ped_total:.2f}).",
            )
        pagos_mixtos_str = json.dumps([leg.model_dump() for leg in data.pagos_mixtos])
        metodo_final = data.pagos_mixtos[0].metodo_pago if len(data.pagos_mixtos) == 1 else "Pago Mixto"
        recibido = round(max(recibido, total_exigible), 2)
        cambio_calculado = 0.0
    else:
        if recibido < total_exigible:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Monto recibido insuficiente. Total a pagar: {total_exigible:.2f} {data.moneda_pago}."
            )
        cambio_calculado = round(recibido - total_exigible, 2)

    factura_num = f"FAC-DD-{pedido.id:06d}"

    pedido.metodo_pago = metodo_final
    pedido.pagos_mixtos_json = pagos_mixtos_str
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
    was_delivered = pedido.estado == "ENTREGADO"
    pedido.estado = "ENTREGADO" if was_delivered else "COBRADO"
    if pedido.tipo == "mesa":
        try:
            refresh_table_state(db, parse_table_number(pedido.numero_mesa))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    pedido.turno_id = turno_activo.id
    current_ventas = float(turno_activo.total_ventas or 0.0)
    turno_activo.total_ventas = round(current_ventas + ped_total, 2)
    turno_activo.total_pedidos += 1
    award_order_loyalty_points(db, pedido)
    record_audit(
        db=db,
        accion="Cobro de pedido",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="pedidos",
        recurso_id=pedido.id,
        detalle=f"Pedido #{pedido.id}: {metodo_final} {data.moneda_pago} {recibido:.2f}",
        auto_commit=False,
    )

    db.commit()

    await ws_manager.broadcast("PAGO_CONFIRMADO", {
        "pedido_id": pedido.id,
        "numero_mesa": pedido.numero_mesa,
        "total": ped_total,
        "factura_numero": factura_num,
        "metodo_pago": metodo_final,
        "cambio": cambio_calculado
    })

    return {
        "mensaje": "Pago procesado exitosamente",
        "pedido_id": pedido.id,
        "factura_numero": factura_num,
        "total": ped_total,
        "propina": float(pedido.propina or 0.0),
        "monto_recibido": recibido,
        "cambio": cambio_calculado,
        "metodo_pago": metodo_final,
        "moneda_pago": pedido.moneda_pago,
        "monto_pago": float(pedido.monto_pago or 0.0),
        "tasa_cambio_pago": float(pedido.tasa_cambio_pago) if pedido.tasa_cambio_pago else None,
        "pagos_mixtos": data.pagos_mixtos or [],
        "repetido": False,
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
        "descuento": float(pedido.descuento or 0.0),
        "propina": float(pedido.propina or 0.0),
        "impuesto_iva": float(pedido.impuesto or 0.0),
        "total": float(pedido.total or 0.0),
        "metodo_pago": pedido.metodo_pago or "Efectivo",
        "pagos_mixtos": json.loads(pedido.pagos_mixtos_json) if pedido.pagos_mixtos_json else [],
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


@router.get("/corte-x")
def get_corte_x_parcial(db: Session = Depends(get_db)):
    """Corte parcial X del turno activo para impresión o revisión sin cerrar caja."""
    turno = db.query(Turno).filter(Turno.activo == True).order_by(Turno.id.desc()).first()
    if not turno:
        raise HTTPException(status_code=404, detail="No hay turno activo para generar Corte X.")
    expected = _expected_shift_totals(db, turno)
    egresos = db.query(func.coalesce(func.sum(MovimientoCaja.monto_usd), 0)).filter(
        MovimientoCaja.turno_id == turno.id,
        MovimientoCaja.tipo == "EGRESO",
    ).scalar()
    propinas = db.query(func.coalesce(func.sum(Pedido.propina), 0)).filter(
        Pedido.turno_id == turno.id,
        Pedido.estado_pago == "PAGADO",
    ).scalar()
    return {
        "numero_turno": turno.numero_turno,
        "fecha_apertura": turno.fecha_apertura.isoformat() if turno.fecha_apertura else None,
        "hora_corte": datetime.now(timezone.utc).isoformat(),
        "monto_apertura": round(float(turno.monto_apertura or 0), 2),
        "total_ventas": round(float(turno.total_ventas or 0), 2),
        "total_pedidos": int(turno.total_pedidos or 0),
        "total_egresos": round(float(egresos or 0), 2),
        "total_propinas": round(float(propinas or 0), 2),
        "esperado_por_metodo": expected,
    }


@router.post("/pedidos/{pedido_id}/dividir")
async def dividir_cuenta_pedido(
    pedido_id: int,
    data: DividirCuentaRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor", "caja"])),
):
    """Divide una cuenta abierta no pagada en partes iguales o por ítems seleccionados."""
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")
    if pedido.estado_pago != "PENDIENTE" or pedido.factura_numero or pedido.estado == "CANCELADO":
        raise HTTPException(status_code=409, detail="Solo pueden dividirse pedidos pendientes de cobro.")

    created_ids: list[int] = []
    if data.modo == "igual":
        partes = int(data.partes or 2)
        if partes < 2:
            raise HTTPException(status_code=422, detail="Debe dividirse en al menos 2 partes.")

        fields = ("subtotal", "impuesto", "costo_empaque", "descuento", "propina")
        shares: list[dict[str, float]] = [{} for _ in range(partes)]
        for field in fields:
            orig_val = round(float(getattr(pedido, field) or 0.0), 2)
            running = 0.0
            for idx in range(partes):
                if idx == partes - 1:
                    val = round(orig_val - running, 2)
                else:
                    val = round(orig_val / partes, 2)
                    running = round(running + val, 2)
                shares[idx][field] = val
        for idx in range(partes):
            shares[idx]["total"] = round(
                shares[idx]["subtotal"]
                + shares[idx]["impuesto"]
                + shares[idx]["costo_empaque"]
                + shares[idx]["propina"],
                2,
            )

        pedido.subtotal = shares[0]["subtotal"]
        pedido.impuesto = shares[0]["impuesto"]
        pedido.costo_empaque = shares[0]["costo_empaque"]
        pedido.descuento = shares[0]["descuento"]
        pedido.propina = shares[0]["propina"]
        pedido.total = shares[0]["total"]
        pedido.observaciones = f"{(pedido.observaciones or '').strip()} [Cuenta 1/{partes}]".strip()

        for idx in range(1, partes):
            child = Pedido(
                numero_mesa=pedido.numero_mesa,
                tipo=pedido.tipo,
                modo_pago=pedido.modo_pago,
                estado=pedido.estado,
                estado_pago="PENDIENTE",
                moneda_pago=pedido.moneda_pago,
                subtotal=shares[idx]["subtotal"],
                impuesto=shares[idx]["impuesto"],
                costo_empaque=shares[idx]["costo_empaque"],
                descuento=shares[idx]["descuento"],
                propina=shares[idx]["propina"],
                total=shares[idx]["total"],
                observaciones=f"Cuenta dividida {idx + 1}/{partes} (Pedido #{pedido.id})",
                nombre_cliente_delivery=pedido.nombre_cliente_delivery,
                telefono_delivery=pedido.telefono_delivery,
                direccion_delivery=pedido.direccion_delivery,
                nombre_factura=pedido.nombre_factura,
                usuario_id=pedido.usuario_id,
                turno_id=pedido.turno_id,
            )
            db.add(child)
            db.flush()
            created_ids.append(child.id)
    else:
        selected_ids = set(data.detalle_ids or [])
        all_details = list(pedido.detalles or [])
        if not selected_ids or len(all_details) < 2:
            raise HTTPException(status_code=422, detail="Selecciona al menos un ítem dejando otros en la cuenta original.")
        moving = [d for d in all_details if d.id in selected_ids]
        keeping = [d for d in all_details if d.id not in selected_ids]
        if not moving or not keeping:
            raise HTTPException(status_code=422, detail="Debes dejar al menos un ítem en la cuenta original.")

        orig_sub = round(sum(float(d.subtotal or 0) for d in all_details), 2)
        tax_ratio = (float(pedido.impuesto or 0) / orig_sub) if orig_sub > 0 else 0.0

        keep_sub = round(sum(float(d.subtotal or 0) for d in keeping), 2)
        keep_tax = round(keep_sub * tax_ratio, 2)
        move_sub = round(sum(float(d.subtotal or 0) for d in moving), 2)
        move_tax = round(float(pedido.impuesto or 0) - keep_tax, 2)

        pedido.subtotal = keep_sub
        pedido.impuesto = keep_tax
        pedido.total = round(keep_sub + keep_tax + float(pedido.costo_empaque or 0) + float(pedido.propina or 0), 2)

        child = Pedido(
            numero_mesa=pedido.numero_mesa,
            tipo=pedido.tipo,
            modo_pago=pedido.modo_pago,
            estado=pedido.estado,
            estado_pago="PENDIENTE",
            moneda_pago=pedido.moneda_pago,
            subtotal=move_sub,
            impuesto=move_tax,
            costo_empaque=0.0,
            descuento=0.0,
            propina=0.0,
            total=round(move_sub + move_tax, 2),
            observaciones=f"Cuenta separada por ítems (Pedido #{pedido.id})",
            nombre_cliente_delivery=pedido.nombre_cliente_delivery,
            telefono_delivery=pedido.telefono_delivery,
            direccion_delivery=pedido.direccion_delivery,
            nombre_factura=pedido.nombre_factura,
            usuario_id=pedido.usuario_id,
            turno_id=pedido.turno_id,
        )
        db.add(child)
        db.flush()
        for det in moving:
            det.pedido_id = child.id
        created_ids.append(child.id)

    record_audit(
        db=db,
        accion="SPLIT_BILL",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="pedidos",
        recurso_id=pedido.id,
        detalle=f"Pedido #{pedido.id} dividido ({data.modo}) -> nuevas cuentas: {created_ids}",
        auto_commit=False,
    )
    db.commit()
    await ws_manager.broadcast("CUENTA_DIVIDIDA", {"pedido_id": pedido.id, "nuevos_pedidos": created_ids})
    return {"mensaje": "Cuenta dividida exitosamente.", "pedido_original_id": pedido.id, "nuevos_pedidos": created_ids}
