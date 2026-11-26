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
from backend.app.services.orders import get_pricing_config, prepare_order_items, deduct_order_stock

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
    
    # Public brand and footer copy are configurable from the admin portal.
    public_defaults = {
        "nombre_restaurante": "DONDE DAVID | FAST FOOD",
        "historia_restaurante": "Las mejores hamburguesas artesanales de res 100% preparadas al instante.",
        "direccion_restaurante": "📍 Valencia • Sede Principal",
        "footer_enlaces_titulo": "ENLACES RÁPIDOS",
        "footer_inicio_texto": "🏠 Inicio",
        "footer_menu_texto": "🍔 Menú Interactivo",
        "footer_puntos_texto": "🎁 Puntos de Fidelidad",
        "footer_atencion_titulo": "HORARIO & ATENCIÓN",
        "horario_atencion": "Todos los días: 11:00 AM - 11:00 PM",
        "servicio_restaurante": "Delivery directo & Pedidos QR en mesa",
        "medios_pago_texto": "Pago Móvil • Zelle • Tarjetas • Efectivo",
        "landing_titulo": "¡BUEN SABOR, RÁPIDO Y RECIÉN HECHO!",
        "landing_descripcion": "Hamburguesas artesanales de carne 100% res, perros calientes con toppings crocantes y malteadas heladas. Pide por QR en mesa o solicita delivery.",
    }
    for key, value in public_defaults.items():
        res.setdefault(key, value)

    legacy_names = {"donde david fresh & tasty!", "donde david - fresh & tasty!"}
    if str(res.get("nombre_restaurante", "")).strip().casefold() in legacy_names:
        res["nombre_restaurante"] = public_defaults["nombre_restaurante"]
    legacy_story = str(res.get("historia_restaurante", "")).casefold()
    if "toon gourmet" in legacy_story or "hamburguesas artesanales gigantes" in legacy_story:
        res["historia_restaurante"] = public_defaults["historia_restaurante"]

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
    if "tiempo_delivery_estimado_minutos" not in res:
        res["tiempo_delivery_estimado_minutos"] = "30"
    res["google_maps_api_key"] = res.get("google_maps_api_key", "").strip()
    if "impuesto_porcentaje" not in res:
        res["impuesto_porcentaje"] = "16.00"
    if "iva_activo" not in res:
        res["iva_activo"] = "true"
        
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
    
    pricing = get_pricing_config(db)
    tax_rate = pricing["tax_rate"]
    delivery_fee = pricing["delivery_fee"] if pedido_in.tipo == "delivery" else 0.0
    costo_empaque_val = pricing["package_fee"] if pedido_in.tipo == "llevar" else 0.0

    deferred_payment = pedido_in.tipo == "mesa" and pedido_in.modo_pago == "PAGAR_DESPUES"
    if pedido_in.modo_pago not in {"PAGAR_ANTES", "PAGAR_DESPUES"}:
        raise HTTPException(status_code=422, detail="La modalidad de cobro no es válida.")
    if pedido_in.modo_pago == "PAGAR_DESPUES" and pedido_in.tipo != "mesa":
        raise HTTPException(status_code=422, detail="La cuenta abierta solo está disponible para pedidos en mesa.")
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

    products, requested_quantities, stock_before, detalles_db, subtotal_final = prepare_order_items(
        db, pedido_in.detalles
    )
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
            else "Delivery"
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
    if pedido_in.tipo == "delivery":
        nuevo_pedido.numero_mesa = f"Delivery #{nuevo_pedido.id + 100}"
    deduct_order_stock(
        db,
        nuevo_pedido.id,
        products,
        requested_quantities,
        stock_before,
        current_user.id if current_user else None,
    )
    db.commit()
    db.refresh(nuevo_pedido)

    if deferred_payment:
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
    elif is_mobile_payment:
        await ws_manager.broadcast("PAGO_MOVIL_PENDIENTE", {
            "id": nuevo_pedido.id,
            "numero_mesa": nuevo_pedido.numero_mesa,
            "total": float(nuevo_pedido.total or 0),
            "monto_pago": float(nuevo_pedido.monto_pago or 0),
            "tipo": nuevo_pedido.tipo,
            "fecha": str(nuevo_pedido.fecha_creacion),
        })
    else:
        await ws_manager.broadcast("PEDIDO_PENDIENTE_COBRO", {
            "id": nuevo_pedido.id,
            "numero_mesa": nuevo_pedido.numero_mesa,
            "total": float(nuevo_pedido.total or 0),
            "metodo_pago": nuevo_pedido.metodo_pago,
            "tipo": nuevo_pedido.tipo,
            "fecha": str(nuevo_pedido.fecha_creacion),
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
        "modo_pago": pedido.modo_pago,
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
    db: Session = Depends(get_db),
    tracking_token: Optional[str] = Header(default=None, alias="X-Order-Tracking-Token"),
    current_user: Optional[Usuario] = Depends(get_current_user_optional),
):
    pedido = db.query(Pedido).filter(Pedido.id == req.pedido_id).with_for_update().first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    is_staff = current_user is not None and current_user.rol in {"admin", "supervisor", "caja", "repartidor"}
    owns_order = current_user is not None and pedido.usuario_id == current_user.id
    has_valid_token = False
    if tracking_token and pedido.token_seguimiento_hash:
        token_digest = hashlib.sha256(tracking_token.encode("utf-8")).hexdigest()
        has_valid_token = hmac.compare_digest(token_digest, pedido.token_seguimiento_hash)
    if not (is_staff or owns_order or has_valid_token):
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if pedido.tipo != "delivery" or pedido.estado == "CANCELADO":
        raise HTTPException(status_code=409, detail="Este pedido no admite verificación OTP.")

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
    locked_user = db.query(Usuario).filter(Usuario.id == current_user.id).with_for_update().first()
    if not locked_user or int(locked_user.puntos_fidelidad or 0) < costo:
        raise HTTPException(status_code=400, detail="Puntos insuficientes para canjear esta recompensa")
    # Deduct points
    locked_user.puntos_fidelidad = int(locked_user.puntos_fidelidad or 0) - costo
    # Log redemption
    db.add(PuntosLog(
        usuario_id=locked_user.id,
        puntos=-costo,
        concepto=f"Canje de {recompensa}",
        pedido_id=None
    ))
    db.commit()
    db.refresh(locked_user)
    return {"mensaje": "Recompensa canjeada exitosamente", "puntos_restantes": locked_user.puntos_fidelidad}


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
