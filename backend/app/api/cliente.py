import hashlib
import json
import logging
import math
import secrets
import hmac
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.rate_limit import limiter
from backend.app.core.security import get_current_user_optional, get_current_user
from backend.app.services.exchange_rate import get_bcv_rate
from backend.app.models.categoria import Categoria
from backend.app.models.producto import Producto
from backend.app.models.pedido import Pedido
from backend.app.models.detalle_pedido import DetallePedido
from backend.app.models.turno import Turno
from backend.app.models.configuracion import Configuracion
from backend.app.models.promocion import Promocion
from backend.app.models.puntos_log import PuntosLog
from backend.app.models.usuario import Usuario
from backend.app.models.mesa import Mesa
from backend.app.models.guia_item import GuiaItem
from backend.app.models.resena import Resena
from backend.app.models.publicacion import Publicacion
from backend.app.models.movimiento_inventario import MovimientoInventario
from backend.app.schemas.schemas import CategoriaOut, ProductoOut, PedidoCreate, PedidoCreadoOut, OTPVerifyRequest, ResenaCreate, ResenaOut, PublicacionOut, CambiarMesaRequest, SolicitudMesaCreate
from backend.app.models.solicitud_mesa import SolicitudMesa
from backend.app.websockets.manager import ws_manager
from backend.app.services.tables import parse_table_number, refresh_table_state

router = APIRouter(prefix="/cliente", tags=["Cliente QR / App"])
logger = logging.getLogger(__name__)

@router.get("/configuraciones-publicas")
def get_configuraciones_publicas(db: Session = Depends(get_db)):
    configs = db.query(Configuracion).all()
    res = {c.clave: c.valor for c in configs}
    rate_status = get_bcv_rate(db)
    if rate_status["tasa_cambio_bs"] is not None:
        res["tasa_cambio_bs"] = str(rate_status["tasa_cambio_bs"])
    res["tasa_fuente"] = rate_status["tasa_fuente"] or ""
    res["tasa_actualizada_at"] = rate_status["tasa_actualizada_at"] or ""
    res["tasa_estado"] = rate_status["tasa_estado"]
    res["tasa_respaldo"] = str(rate_status["tasa_respaldo"]).lower()
    
    # Defaults
    if "historia_restaurante" not in res:
        res["historia_restaurante"] = "Donde David comenzó con la pasión por ofrecer las mejores hamburguesas y perros al estilo Toon Gourmet en un ambiente divertido y tecnológico."
    if "instagram_link" not in res:
        res["instagram_link"] = "https://instagram.com/dondedavid"
    if "tiktok_link" not in res:
        res["tiktok_link"] = "https://tiktok.com/@dondedavid"
    if "whatsapp_contacto" not in res:
        res["whatsapp_contacto"] = "+502 4112 5554"
    if "costo_empaque" not in res:
        res["costo_empaque"] = "3.00"
    if "costo_delivery" not in res:
        res["costo_delivery"] = "5.00"
    if "costo_empaque" not in res:
        res["costo_empaque"] = "3.00"
    if "tiempo_delivery_estimado_minutos" not in res:
        res["tiempo_delivery_estimado_minutos"] = "30"
    res["google_maps_api_key"] = res.get("google_maps_api_key", "").strip()
    if "impuesto_porcentaje" not in res:
        res["impuesto_porcentaje"] = "16.00"
        
    return res

@router.get("/publicaciones", response_model=List[PublicacionOut])
def get_publicaciones_publicas(db: Session = Depends(get_db)):
    return db.query(Publicacion).filter(Publicacion.activo == True).order_by(Publicacion.fecha_creacion.desc()).all()

@router.get("/promociones")
def get_promociones(db: Session = Depends(get_db)):
    return (
        db.query(Promocion)
        .filter(Promocion.activo == True)
        .order_by(Promocion.id.asc())
        .all()
    )

@router.get("/resenas", response_model=List[ResenaOut])
def get_resenas_publicas(db: Session = Depends(get_db)):
    return db.query(Resena).filter(Resena.activo == True).order_by(Resena.fecha_creacion.desc()).all()

@router.post("/resenas", response_model=ResenaOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def crear_resena_publica(
    request: Request,
    response: Response,
    resena_in: ResenaCreate,
    db: Session = Depends(get_db)
):
    nueva = Resena(
        nombre_cliente=resena_in.nombre_cliente,
        comentario=resena_in.comentario,
        estrellas=resena_in.estrellas or 5,
        foto_url=resena_in.foto_url
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva

@router.get("/guia")
def get_guia_cliente(tipo: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(GuiaItem).filter(GuiaItem.activo == True)
    if tipo:
        query = query.filter(GuiaItem.tipo_vista.in_([tipo, "ambos"]))
    return query.order_by(GuiaItem.orden.asc()).all()

@router.get("/categorias", response_model=List[CategoriaOut])
def get_categorias(db: Session = Depends(get_db)):
    return db.query(Categoria).filter(Categoria.activo == True).order_by(Categoria.orden.asc()).all()

@router.get("/productos", response_model=List[ProductoOut])
def get_productos(categoria_id: Optional[int] = None, search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Producto).filter(
        Producto.activo == True,
        Producto.disponible == True,
        Producto.stock > 0,
    )
    if categoria_id:
        query = query.filter(Producto.categoria_id == categoria_id)
    if search:
        query = query.filter(Producto.nombre.ilike(f"%{search}%"))
    return query.all()

@router.post("/pedidos", response_model=PedidoCreadoOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
async def crear_pedido(
    request: Request,
    response: Response,
    pedido_in: PedidoCreate, 
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_optional)
):
    if not pedido_in.detalles or len(pedido_in.detalles) == 0:
        raise HTTPException(status_code=400, detail="El pedido debe contener productos.")
    
    tax_config = db.query(Configuracion).filter(Configuracion.clave == "impuesto_porcentaje").first()
    tax_rate = float(tax_config.valor) if tax_config else 16.0

    delivery_config = db.query(Configuracion).filter(Configuracion.clave == "costo_delivery").first()
    delivery_fee = float(delivery_config.valor) if pedido_in.tipo == "delivery" and delivery_config else (5.0 if pedido_in.tipo == "delivery" else 0.0)

    empaque_config = db.query(Configuracion).filter(Configuracion.clave == "costo_empaque").first()
    costo_empaque_val = float(empaque_config.valor) if pedido_in.tipo == "llevar" and empaque_config else (3.0 if pedido_in.tipo == "llevar" else 0.0)

    deferred_payment = pedido_in.tipo == "mesa" and pedido_in.modo_pago == "PAGAR_DESPUES"
    metodo_pago = None if deferred_payment else (pedido_in.metodo_pago or "Efectivo")
    moneda_pago = pedido_in.moneda_pago or "USD"
    if not deferred_payment and metodo_pago not in {"Pago Móvil", "Efectivo", "Punto de Venta"}:
        raise HTTPException(status_code=422, detail="Método de pago no admitido.")
    if not deferred_payment and metodo_pago == "Pago Móvil":
        if moneda_pago != "VES" or not pedido_in.referencia_pago or not pedido_in.referencia_pago.strip():
            raise HTTPException(status_code=422, detail="Pago Móvil requiere moneda Bs. y una referencia de pago.")
        required_bank_config = db.query(Configuracion).filter(
            Configuracion.clave.in_([
                "pago_movil_banco",
                "pago_movil_telefono",
                "pago_movil_rif",
                "pago_movil_titular",
            ])
        ).all()
        if len(required_bank_config) != 4 or any(not item.valor.strip() for item in required_bank_config):
            raise HTTPException(status_code=409, detail="El restaurante todavía no configuró los datos de Pago Móvil.")
    elif not deferred_payment and pedido_in.referencia_pago:
        raise HTTPException(status_code=422, detail="La referencia solo aplica a Pago Móvil.")

    rate_status = get_bcv_rate(db) if moneda_pago == "VES" and not deferred_payment else None
    if not deferred_payment and moneda_pago == "VES" and rate_status["tasa_cambio_bs"] is None:
        raise HTTPException(status_code=503, detail="No hay una tasa BCV válida disponible para pagos en bolívares.")
    rate_snapshot = rate_status["tasa_cambio_bs"] if rate_status else None

    turno_activo = db.query(Turno).filter(Turno.activo == True).order_by(Turno.id.desc()).first()
    turno_id = turno_activo.id if turno_activo else None

    # Validar Mesa si es en local
    num_mesa_clean = pedido_in.numero_mesa.strip()
    if pedido_in.tipo == "mesa":
        try:
            mesa_num_val = int(num_mesa_clean.lower().replace("mesa", "").strip())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="El número de mesa no es válido.") from exc
        mesa_obj = db.query(Mesa).filter(Mesa.numero_mesa == mesa_num_val).with_for_update().first()
        if not mesa_obj:
            raise HTTPException(status_code=404, detail=f"La Mesa #{mesa_num_val} no existe.")
        if mesa_obj.estado in {"PENDIENTE_LIMPIEZA", "EN_LIMPIEZA"}:
            raise HTTPException(status_code=409, detail="La mesa debe quedar limpia antes de recibir otro pedido.")
        mesa_obj.estado = "OCUPADA"
        mesa_obj.cliente_actual = current_user.nombre if current_user else f"Cliente Mesa {mesa_num_val}"

    requested_quantities: dict[int, int] = {}
    for item in pedido_in.detalles:
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
            raise HTTPException(status_code=404, detail=f"Producto con ID {product_id} no disponible.")
        if product.stock < quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stock insuficiente para el producto '{product.nombre}' (Disponible: {product.stock}, Solicitado: {quantity})."
            )
        products[product_id] = product
        stock_before[product_id] = product.stock

    subtotal_acumulado = 0.0
    detalles_db = []

    for item in pedido_in.detalles:
        producto = products[item.producto_id]
        precio = float(producto.precio_promocion) if (producto.precio_promocion and producto.precio_promocion > 0) else float(producto.precio)
        customizations = item.personalizaciones or {}
        extras_requested = customizations.get("extras", [])
        if not isinstance(extras_requested, list):
            raise HTTPException(status_code=422, detail="La lista de extras no es válida.")
        try:
            configured_extras = json.loads(producto.extras_json or "[]")
        except json.JSONDecodeError:
            logger.exception("Invalid extras_json for product %s", producto.id)
            raise HTTPException(status_code=500, detail="La configuración de extras de un producto es inválida.")
        if not isinstance(configured_extras, list):
            logger.error("Invalid extras_json shape for product %s", producto.id)
            raise HTTPException(status_code=500, detail="La configuración de extras de un producto es inválida.")
        configured_by_name = {
            entry["nombre"]: float(entry["precio"])
            for entry in configured_extras
            if isinstance(entry, dict)
            and isinstance(entry.get("nombre"), str)
            and isinstance(entry.get("precio"), (int, float))
            and not isinstance(entry.get("precio"), bool)
            and math.isfinite(entry["precio"])
        }
        selected_names = []
        extra_total = 0.0
        for extra in extras_requested:
            if not isinstance(extra, str) or extra not in configured_by_name or extra in selected_names:
                raise HTTPException(status_code=422, detail=f"El extra solicitado no está disponible para {producto.nombre}.")
            selected_names.append(extra)
            extra_total += configured_by_name[extra]
        unit_price = round(precio + extra_total, 2)
        subtotal_item = round(unit_price * item.cantidad, 2)
        subtotal_acumulado += subtotal_item

        personalizations_to_save = dict(customizations)
        if extras_requested:
            personalizations_to_save["extras"] = selected_names
        personalizaciones_str = json.dumps(personalizations_to_save) if personalizations_to_save else None

        detalle = DetallePedido(
            producto_id=producto.id,
            cantidad=item.cantidad,
            precio_unitario=unit_price,
            subtotal=subtotal_item,
            puntos_fidelidad_unitarios=max(0, int(producto.puntos_fidelidad or 0)),
            personalizaciones=personalizaciones_str,
            observaciones=item.observaciones,
            estado="PENDIENTE"
        )
        detalles_db.append(detalle)

    for product_id, quantity in requested_quantities.items():
        products[product_id].stock -= quantity

    subtotal_final = round(subtotal_acumulado, 2)
    impuesto_monto = round(subtotal_final * (tax_rate / 100.0), 2)
    total_final = round(subtotal_final + impuesto_monto + delivery_fee + costo_empaque_val, 2)

    # Generar código OTP de 6 dígitos
    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    tracking_token = secrets.token_urlsafe(32)

    is_mobile_payment = metodo_pago == "Pago Móvil"
    nuevo_pedido = Pedido(
        numero_mesa=(
            num_mesa_clean if pedido_in.tipo == "mesa"
            else "Mostrador" if pedido_in.tipo == "llevar"
            else f"Delivery #{db.query(Pedido).count() + 101}"
        ),
        codigo_qr=pedido_in.codigo_qr,
        token_seguimiento_hash=hashlib.sha256(tracking_token.encode("utf-8")).hexdigest(),
        tipo=pedido_in.tipo or "mesa",
        modo_pago=pedido_in.modo_pago or "PAGAR_ANTES",
        estado="PAGO_PENDIENTE" if is_mobile_payment else "PENDIENTE",
        subtotal=subtotal_final,
        impuesto=impuesto_monto,
        costo_empaque=costo_empaque_val,
        descuento=0.0,
        total=total_final,
        metodo_pago=metodo_pago,
        estado_pago="PENDIENTE_VALIDACION" if is_mobile_payment else "PENDIENTE",
        moneda_pago=moneda_pago,
        monto_pago=None if deferred_payment else (round(total_final * rate_snapshot, 2) if moneda_pago == "VES" else total_final),
        tasa_cambio_pago=rate_snapshot,
        referencia_pago=pedido_in.referencia_pago.strip() if pedido_in.referencia_pago else None,
        estado_delivery="PENDIENTE" if pedido_in.tipo == "delivery" else None,
        observaciones=pedido_in.observaciones,
        nombre_cliente_delivery=pedido_in.nombre_cliente_delivery or (current_user.nombre if current_user else "Cliente Local"),
        telefono_delivery=pedido_in.telefono_delivery,
        direccion_delivery=pedido_in.direccion_delivery,
        delivery_lat=pedido_in.delivery_lat if pedido_in.tipo == "delivery" else None,
        delivery_lng=pedido_in.delivery_lng if pedido_in.tipo == "delivery" else None,
        nombre_factura=pedido_in.nombre_cliente_delivery or (current_user.nombre if current_user else "Consumidor Final"),
        codigo_otp=otp_code,
        otp_verificado=False,
        codigo_retiro=f"{secrets.randbelow(900000) + 100000:06d}" if pedido_in.tipo == "llevar" else None,
        estado_retiro="PENDIENTE" if pedido_in.tipo == "llevar" else None,
        usuario_id=current_user.id if current_user else None,
        turno_id=turno_id,
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
            usuario_id=current_user.id if current_user else None
        ))
    db.commit()
    db.refresh(nuevo_pedido)

    if not is_mobile_payment:
        await ws_manager.broadcast("NUEVO_PEDIDO", {
            "id": nuevo_pedido.id,
            "numero_mesa": nuevo_pedido.numero_mesa,
            "estado": nuevo_pedido.estado,
            "modo_pago": nuevo_pedido.modo_pago,
            "total": nuevo_pedido.total,
            "tipo": nuevo_pedido.tipo,
            "detalles_count": len(nuevo_pedido.detalles),
            "fecha": str(nuevo_pedido.fecha_creacion)
        })

    response_order = PedidoCreadoOut.model_validate(nuevo_pedido)
    response_order.codigo_otp = None
    response_order.token_seguimiento = tracking_token
    return response_order


@router.get("/pedidos/{pedido_id}/seguimiento")
@limiter.limit("30/minute")
def obtener_seguimiento_pedido(
    request: Request,
    response: Response,
    pedido_id: int,
    db: Session = Depends(get_db),
    tracking_token: Optional[str] = Header(default=None, alias="X-Order-Tracking-Token"),
    current_user: Optional[Usuario] = Depends(get_current_user_optional),
):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    owns_order = (
        current_user is not None
        and current_user.rol == "cliente"
        and pedido.usuario_id == current_user.id
    )
    has_valid_tracking_token = False
    if tracking_token and pedido.token_seguimiento_hash:
        token_digest = hashlib.sha256(tracking_token.encode("utf-8")).hexdigest()
        has_valid_tracking_token = hmac.compare_digest(token_digest, pedido.token_seguimiento_hash)
    if not owns_order and not has_valid_tracking_token:
        raise HTTPException(status_code=404, detail="Pedido no encontrado.")

    return {
        "id": pedido.id,
        "tipo": pedido.tipo,
        "numero_mesa": pedido.numero_mesa,
        "estado": pedido.estado,
        "estado_pago": pedido.estado_pago,
        "estado_delivery": pedido.estado_delivery,
        "estado_pago": pedido.estado_pago,
        "estado_retiro": pedido.estado_retiro,
        "total": float(pedido.total or 0),
        "subtotal": float(pedido.subtotal or 0),
        "impuesto": float(pedido.impuesto or 0),
        "costo_empaque": float(pedido.costo_empaque or 0),
        "moneda_pago": pedido.moneda_pago,
        "monto_pago": float(pedido.monto_pago) if pedido.monto_pago is not None else None,
        "tasa_cambio_pago": float(pedido.tasa_cambio_pago) if pedido.tasa_cambio_pago is not None else None,
        "metodo_pago": pedido.metodo_pago,
        "fecha_creacion": pedido.fecha_creacion,
        "fecha_pago": pedido.fecha_pago,
        "fecha_entrega": pedido.fecha_entrega,
        "fecha_retiro": pedido.fecha_retiro,
        "direccion_delivery": pedido.direccion_delivery,
        "delivery_lat": float(pedido.delivery_lat) if pedido.delivery_lat is not None else None,
        "delivery_lng": float(pedido.delivery_lng) if pedido.delivery_lng is not None else None,
        "repartidor_lat": float(pedido.repartidor_lat) if pedido.repartidor_lat is not None else None,
        "repartidor_lng": float(pedido.repartidor_lng) if pedido.repartidor_lng is not None else None,
        "ubicacion_repartidor_actualizada_at": pedido.ubicacion_repartidor_actualizada_at,
        "repartidor_nombre": (
            f"{pedido.repartidor.nombre} {pedido.repartidor.apellido}"
            if pedido.repartidor else None
        ),
        "repartidor_telefono": pedido.repartidor.telefono if pedido.repartidor else None,
        "codigo_otp": (
            pedido.codigo_otp
            if pedido.tipo == "delivery"
            and pedido.estado != "CANCELADO"
            and pedido.estado_delivery == "EN_CAMINO"
            else None
        ),
    }

@router.post("/pedidos/{pedido_id}/cambiar-mesa")
@limiter.limit("10/minute")
async def cliente_cambiar_mesa(
    request: Request,
    response: Response,
    pedido_id: int,
    data: CambiarMesaRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if pedido.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para cambiar esta mesa.")
    if pedido.tipo != "mesa" or pedido.estado in ["COBRADO", "ENTREGADO", "CANCELADO"]:
        raise HTTPException(status_code=409, detail="Este pedido ya no puede cambiar de mesa.")

    nueva_mesa_num = data.nueva_mesa
    nueva_mesa_obj = db.query(Mesa).filter(
        Mesa.numero_mesa == nueva_mesa_num
    ).with_for_update().first()
    if not nueva_mesa_obj:
        raise HTTPException(status_code=404, detail=f"La Mesa #{nueva_mesa_num} no existe")
    try:
        mesa_anterior_num = parse_table_number(pedido.numero_mesa)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="No se pudo determinar la mesa actual del pedido.") from exc
    if mesa_anterior_num == nueva_mesa_num:
        raise HTTPException(status_code=409, detail="El pedido ya está asignado a esa mesa.")
    if nueva_mesa_obj.estado != "LIBRE":
        raise HTTPException(status_code=409, detail="La nueva mesa no está disponible.")

    nueva_mesa_obj.estado = "OCUPADA"
    nueva_mesa_obj.cliente_actual = pedido.nombre_factura or f"Cliente Mesa #{nueva_mesa_num}"

    pedido.numero_mesa = f"Mesa {nueva_mesa_num}"
    refresh_table_state(db, mesa_anterior_num)
    db.commit()

    await ws_manager.broadcast("CAMBIO_ESTADO_PEDIDO", {
        "pedido_id": pedido.id,
        "nuevo_estado": pedido.estado,
        "numero_mesa": pedido.numero_mesa,
        "accion": "CAMBIO_MESA_CLIENTE"
    })

    return {"mensaje": f"Has cambiado exitosamente a Mesa #{nueva_mesa_num}", "nueva_mesa": f"Mesa {nueva_mesa_num}"}

@router.post("/pedidos/verificar-otp")
@limiter.limit("10/minute")
def verificar_otp_pedido(
    request: Request,
    response: Response,
    req: OTPVerifyRequest,
    db: Session = Depends(get_db)
):
    pedido = db.query(Pedido).filter(Pedido.id == req.pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    
    if pedido.codigo_otp and hmac.compare_digest(pedido.codigo_otp, req.codigo_otp):
        pedido.otp_verificado = True
        db.commit()
        return {"valido": True, "mensaje": "Verificación OTP completada exitosamente"}
    else:
        raise HTTPException(status_code=400, detail="Código OTP incorrecto. Por favor verifica e intenta de nuevo.")

@router.get("/pedidos/historial")
def get_historial_pedidos(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    pedidos = db.query(Pedido).filter(Pedido.usuario_id == current_user.id).order_by(Pedido.fecha_creacion.desc()).all()
    return pedidos


@router.get("/personalizacion")
def get_personalizacion_cliente(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    orders = (
        db.query(Pedido)
        .filter(
            Pedido.usuario_id == current_user.id,
            Pedido.estado_pago == "PAGADO",
            Pedido.estado != "CANCELADO",
        )
        .order_by(Pedido.fecha_creacion.desc())
        .limit(40)
        .all()
    )
    valid_orders = [
        order for order in orders
        if order.detalles
    ]
    latest = valid_orders[0] if valid_orders else None
    bought_counts = {}
    pair_counts = {}
    recent_order_product_ids = set()
    for order in valid_orders:
        product_ids = {
            detail.producto_id for detail in order.detalles
            if detail.producto_id is not None
        }
        if order is latest:
            recent_order_product_ids = product_ids
        for detail in order.detalles:
            bought_counts[detail.producto_id] = bought_counts.get(detail.producto_id, 0) + detail.cantidad
        for product_id in product_ids:
            pair_counts[product_id] = pair_counts.get(product_id, {})
            for co_product_id in product_ids - {product_id}:
                pair_counts[product_id][co_product_id] = (
                    pair_counts[product_id].get(co_product_id, 0) + 1
                )

    popular_rows = (
        db.query(DetallePedido.producto_id, func.sum(DetallePedido.cantidad).label("unidades"))
        .join(Pedido, Pedido.id == DetallePedido.pedido_id)
        .filter(Pedido.estado_pago == "PAGADO")
        .group_by(DetallePedido.producto_id)
        .all()
    )
    popular_counts = {row.producto_id: int(row.unidades or 0) for row in popular_rows}
    available_products = (
        db.query(Producto)
        .filter(Producto.activo == True, Producto.disponible == True, Producto.stock > 0)
        .all()
    )
    last_product_ids = recent_order_product_ids
    scored_products = []
    for product in available_products:
        if product.id in last_product_ids:
            continue
        pair_score = sum(
            counts.get(product.id, 0) for counts in pair_counts.values()
        )
        score = (
            pair_score * 3
            + min(bought_counts.get(product.id, 0), 6) * 0.5
            + popular_counts.get(product.id, 0) * 0.05
        )
        if score > 0:
            scored_products.append((score, popular_counts.get(product.id, 0), pair_score, product))

    scored_products.sort(key=lambda row: (-row[0], -row[1], row[3].nombre.casefold()))

    last_order = None
    if latest:
        last_order = {
            "id": latest.id,
            "total": float(latest.total or 0),
            "fecha_creacion": latest.fecha_creacion,
            "items": [
                {
                    "producto_id": detail.producto_id,
                    "nombre": detail.producto.nombre if detail.producto else "Producto no disponible",
                    "cantidad": detail.cantidad,
                    "precio_unitario": float(detail.precio_unitario or 0),
                    "subtotal": float(detail.subtotal or 0),
                    "personalizaciones": detail.personalizaciones,
                }
                for detail in latest.detalles
            ],
        }

    return {
        "saludo": f"¡Hola, {current_user.nombre}!",
        "puntos_fidelidad": int(current_user.puntos_fidelidad or 0),
        "ultima_orden": last_order,
        "recomendaciones": [
            {
                "id": product.id,
                "nombre": product.nombre,
                "descripcion": product.descripcion,
                "precio": float(product.precio_promocion or product.precio or 0),
                "imagen_url": product.imagen_url,
                "stock": product.stock,
                "puntos_fidelidad": int(product.puntos_fidelidad or 0),
                "unidades_vendidas": popular_counts.get(product.id, 0),
                "motivo": (
                    "Combinación basada en tus pedidos" if pair_score
                    else "Ya lo has pedido antes" if bought_counts.get(product.id, 0)
                    else "Popular entre nuestros clientes"
                ),
            }
            for _, _, pair_score, product in scored_products[:3]
        ],
    }


@router.post("/solicitudes-mesa", status_code=status.HTTP_201_CREATED)
@limiter.limit("6/minute")
async def crear_solicitud_mesa(
    request: Request,
    response: Response,
    data: SolicitudMesaCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user_optional),
):
    mesa = db.query(Mesa).filter(Mesa.numero_mesa == data.numero_mesa).first()
    if not mesa:
        raise HTTPException(status_code=404, detail="La mesa indicada no existe.")
    if data.pedido_id:
        pedido = db.query(Pedido).filter(
            Pedido.id == data.pedido_id,
            Pedido.tipo == "mesa",
            Pedido.numero_mesa.in_([str(data.numero_mesa), f"Mesa {data.numero_mesa}"]),
        ).first()
        if not pedido:
            raise HTTPException(status_code=404, detail="El pedido no corresponde a esta mesa.")
    existing = db.query(SolicitudMesa).filter(
        SolicitudMesa.mesa_id == mesa.id,
        SolicitudMesa.tipo == data.tipo,
        SolicitudMesa.estado == "PENDIENTE",
    ).order_by(SolicitudMesa.id.desc()).first()
    if existing:
        return {
            "id": existing.id,
            "mesa": mesa.numero_mesa,
            "tipo": existing.tipo,
            "estado": existing.estado,
            "mensaje": "Ya hay una solicitud igual pendiente para esta mesa.",
        }
    solicitud = SolicitudMesa(
        mesa_id=mesa.id,
        pedido_id=data.pedido_id,
        usuario_id=current_user.id if current_user else None,
        tipo=data.tipo,
        nota=data.nota.strip() if data.nota else None,
    )
    db.add(solicitud)
    db.commit()
    db.refresh(solicitud)
    await ws_manager.broadcast("SOLICITUD_MESA", {
        "id": solicitud.id,
        "mesa": mesa.numero_mesa,
        "tipo": solicitud.tipo,
        "estado": solicitud.estado,
    })
    return {
        "id": solicitud.id,
        "mesa": mesa.numero_mesa,
        "tipo": solicitud.tipo,
        "estado": solicitud.estado,
        "mensaje": "Solicitud enviada al equipo de sala.",
    }
@router.post("/puntos/canjear")
def canjear_puntos(
    recompensa: str = Query(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    # Define reward cost mapping (hardcoded)
    reward_costs = {
        "Papas Gratis": 100,
        "Bebida Gratis": 50,
        "Descuento 10%": 150,
    }
    if recompensa not in reward_costs:
        raise HTTPException(status_code=400, detail="Recompensa no válida")
    costo = reward_costs[recompensa]
    if current_user.puntos_fidelidad < costo:
        raise HTTPException(status_code=400, detail="Puntos insuficientes para canjear esta recompensa")
    # Deduct points
    current_user.puntos_fidelidad -= costo
    # Log redemption
    db.add(PuntosLog(
        usuario_id=current_user.id,
        puntos=-costo,
        concepto=f"Canje de {recompensa}",
        pedido_id=None
    ))
    db.commit()
    db.refresh(current_user)
    return {"mensaje": "Recompensa canjeada exitosamente", "puntos_restantes": current_user.puntos_fidelidad}


@router.get("/puntos/historial")
def get_puntos_historial(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    logs = db.query(PuntosLog).filter(PuntosLog.usuario_id == current_user.id).order_by(PuntosLog.fecha.desc()).all()
    return {
        "puntos_actuales": current_user.puntos_fidelidad,
        "historial": [
            {"id": l.id, "puntos": l.puntos, "concepto": l.concepto, "fecha": str(l.fecha)}
            for l in logs
        ]
    }
