import json
import math
import secrets
from typing import List, Literal, Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hmac
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, or_
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
from backend.app.models.puntos_log import Auditoria
from backend.app.models.arqueo_turno import ArqueoTurno
from backend.app.schemas.schemas import PedidoOut, TurnoApertura, TurnoCierre, TurnoOut, CobrarPedidoRequest, DetallePedidoItem, MovimientoCajaCreate, MovimientoCajaOut, ConfirmarRetiroRequest
from backend.app.schemas.schemas import ConfirmarPagoRequest
from backend.app.services.exchange_rate import get_bcv_rate
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
                refresh_table_state(db, parse_table_number(pedido.numero_mesa))
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
        message = "Pago rechazado y pedido cancelado."

    audit_detail = f"Pedido #{pedido.id}: {'aprobado' if data.aprobado else 'rechazado'}"
    if data.observacion and data.observacion.strip():
        audit_detail += f" · {data.observacion.strip()}"
    db.add(Auditoria(
        accion="Validación de Pago Móvil",
        usuario=current_user.nombre_usuario,
        detalle=audit_detail[:255],
    ))

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

    iva_active_cfg = db.query(Configuracion).filter(Configuracion.clave == "iva_activo").first()
    is_iva_active = iva_active_cfg.valor.lower() in ("true", "1") if iva_active_cfg else True
    tax_config = db.query(Configuracion).filter(Configuracion.clave == "impuesto_porcentaje").first()
    tax_rate = (float(tax_config.valor) if tax_config else 16.0) if is_iva_active else 0.0
    delivery_config = db.query(Configuracion).filter(Configuracion.clave == "costo_delivery").first()
    package_config = db.query(Configuracion).filter(Configuracion.clave == "costo_empaque").first()
    delivery_fee = float(delivery_config.valor) if delivery_config else 5.0
    package_fee = float(package_config.valor) if package_config else 3.0

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
        customizations = item.personalizaciones or {}
        extras_requested = customizations.get("extras", [])
        if not isinstance(extras_requested, list):
            raise HTTPException(status_code=422, detail="La lista de extras no es válida.")
        try:
            configured_extras = json.loads(producto.extras_json or "[]")
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=500, detail="La configuración de extras de un producto es inválida.") from exc
        if not isinstance(configured_extras, list):
            raise HTTPException(status_code=500, detail="La configuración de extras de un producto es inválida.")
        configured_by_name = {
            entry["nombre"]: float(entry["precio"])
            for entry in configured_extras
            if isinstance(entry, dict)
            and isinstance(entry.get("nombre"), str)
            and isinstance(entry.get("precio"), (int, float))
            and not isinstance(entry.get("precio"), bool)
            and math.isfinite(entry["precio"])
            and entry["precio"] >= 0
        }
        selected_names = []
        extra_total = 0.0
        for extra in extras_requested:
            if not isinstance(extra, str) or extra not in configured_by_name or extra in selected_names:
                raise HTTPException(status_code=422, detail=f"El extra solicitado no está disponible para {producto.nombre}.")
            selected_names.append(extra)
            extra_total += configured_by_name[extra]
        unit_price = round(precio_num + extra_total, 2)
        subtotal_item = round(unit_price * item.cantidad, 2)
        subtotal_acumulado += subtotal_item

        detalle = DetallePedido(
            producto_id=producto.id,
            cantidad=item.cantidad,
            precio_unitario=unit_price,
            subtotal=subtotal_item,
            puntos_fidelidad_unitarios=max(0, int(producto.puntos_fidelidad or 0)),
            personalizaciones=json.dumps({**customizations, "extras": selected_names}) if customizations else None,
            observaciones=item.observaciones,
            estado="PENDIENTE"
        )
        detalles_db.append(detalle)

    subtotal_final = round(subtotal_acumulado, 2)
    impuesto_monto = round(subtotal_final * (tax_rate / 100.0), 2)
    costo_extra = delivery_fee if data.tipo == "delivery" else package_fee if data.tipo == "llevar" else 0.0
    total_final = round(subtotal_final + impuesto_monto + costo_extra, 2)

    rate_status = get_bcv_rate(db) if data.moneda_pago == "VES" else None
    exchange_rate = rate_status["tasa_cambio_bs"] if rate_status else None
    if data.moneda_pago == "VES" and exchange_rate is None:
        raise HTTPException(status_code=503, detail="No hay una tasa BCV válida para cobrar en bolívares.")
    total_exigible = round(total_final * exchange_rate, 2) if exchange_rate else total_final
    if data.monto_recibido < total_exigible:
        currency_mark = "Bs. " if data.moneda_pago == "VES" else "$"
        raise HTTPException(
            status_code=400,
            detail=f"Monto recibido ({currency_mark}{data.monto_recibido:.2f}) insuficiente. Total: {currency_mark}{total_exigible:.2f}",
        )

    cambio_calculado = round(data.monto_recibido - total_exigible, 2)
    for product_id, quantity in requested_quantities.items():
        products[product_id].stock -= quantity

    nuevo_pedido = Pedido(
        numero_mesa=numero_mesa if data.tipo == "mesa" else "Mostrador" if data.tipo == "llevar" else f"Delivery #{db.query(Pedido).count() + 101}",
        tipo=data.tipo,
        modo_pago="PAGAR_ANTES",
        estado="COBRADO",
        subtotal=subtotal_final,
        impuesto=impuesto_monto,
        costo_empaque=package_fee if data.tipo == "llevar" else 0.0,
        descuento=0.0,
        total=total_final,
        metodo_pago=data.metodo_pago,
        monto_recibido=data.monto_recibido,
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
    award_order_loyalty_points(db, nuevo_pedido)
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
        "metodo_pago": data.metodo_pago,
        "moneda_pago": data.moneda_pago,
        "monto_pago": total_exigible,
        "tasa_cambio_pago": exchange_rate,
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

    rate_status = get_bcv_rate(db) if data.moneda_pago == "VES" else None
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
    db.add(Auditoria(
        accion="Cobro de pedido",
        usuario=current_user.nombre_usuario,
        detalle=f"Pedido #{pedido.id}: {data.metodo_pago} {data.moneda_pago} {recibido:.2f}",
    ))

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
