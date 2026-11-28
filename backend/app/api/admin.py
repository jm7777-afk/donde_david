import os
import io
import csv
import uuid
import hashlib
import logging
import math
import tempfile
import json
from urllib.parse import quote, urlsplit
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Literal
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, File, Query, UploadFile, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, EmailStr, Field, field_validator
from backend.app.core.database import get_db
from backend.app.core.security import require_roles, get_password_hash
from backend.app.models.usuario import Usuario
from backend.app.models.categoria import Categoria
from backend.app.models.producto import Producto
from backend.app.models.producto_insumo import ProductoInsumo
from backend.app.models.pedido import Pedido
from backend.app.models.detalle_pedido import DetallePedido
from backend.app.models.turno import Turno
from backend.app.models.configuracion import Configuracion
from backend.app.models.insumo import Insumo
from backend.app.models.mesa import Mesa
from backend.app.models.promocion import Promocion
from backend.app.models.puntos_log import Auditoria
from backend.app.models.guia_item import GuiaItem
from backend.app.models.resena import Resena
from backend.app.models.publicacion import Publicacion
from backend.app.models.movimiento_inventario import MovimientoInventario
from backend.app.models.movimiento_caja import MovimientoCaja
from backend.app.schemas.schemas import RecetaUpdateRequest
from backend.app.services.exchange_rate import get_bcv_rate
from backend.app.services.audit_service import record_audit
from backend.app.websockets.manager import ws_manager

router = APIRouter(
    prefix="/admin",
    tags=["Administración"],
    dependencies=[Depends(require_roles(["admin", "supervisor"]))]
)

class IngresoCreate(BaseModel):
    concepto: str = Field(min_length=1, max_length=150)
    monto: float = Field(gt=0, allow_inf_nan=False)

class MesaCreate(BaseModel):
    numero_mesa: int = Field(gt=0)
    capacidad: Optional[int] = Field(default=4, gt=0)
    zona: Optional[str] = Field(default="Salón", max_length=40)


class MesaUpdate(BaseModel):
    capacidad: Optional[int] = Field(default=None, gt=0)
    zona: Optional[str] = Field(default=None, min_length=1, max_length=40)

class InsumoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    stock_actual: float = Field(ge=0, allow_inf_nan=False)
    stock_minimo: float = Field(ge=0, allow_inf_nan=False)
    unidad_medida: str = Field(min_length=1, max_length=20)
    costo_unitario: float = Field(default=0.0, ge=0, allow_inf_nan=False)

class InsumoIngreso(BaseModel):
    cantidad: float = Field(gt=0, allow_inf_nan=False)
    costo_unitario: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    proveedor: Optional[str] = Field(default=None, max_length=150)


class CompraInventarioCreate(BaseModel):
    insumo_id: Optional[int] = Field(default=None, gt=0)
    producto_id: Optional[int] = Field(default=None, gt=0)
    cantidad: float = Field(gt=0, allow_inf_nan=False)
    costo_unitario: float = Field(ge=0, allow_inf_nan=False)
    proveedor: Optional[str] = Field(default=None, max_length=150)
    motivo: Optional[str] = Field(default="Compra / Reabastecimiento", max_length=255)

class CategoriaCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None
    orden: Optional[int] = 0

class ProductoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    descripcion: Optional[str] = None
    precio: float = Field(ge=0, allow_inf_nan=False)
    precio_promocion: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    costo_unitario: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    categoria_id: int = Field(gt=0)
    imagen_url: Optional[str] = None
    stock: Optional[int] = Field(default=50, ge=0)
    puntos_fidelidad: int = Field(default=0, ge=0, le=100000)
    tiempo_preparacion: int = Field(default=15, ge=1, le=240)
    ingredientes_json: Optional[str] = None
    extras_json: Optional[str] = None
    media_json: Optional[str] = None
    alergenos: Optional[str] = Field(default=None, max_length=500)
    disponible: bool = True

class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    precio_promocion: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    costo_unitario: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    stock: Optional[int] = Field(default=None, ge=0)
    puntos_fidelidad: Optional[int] = Field(default=None, ge=0, le=100000)
    tiempo_preparacion: Optional[int] = Field(default=None, ge=1, le=240)
    imagen_url: Optional[str] = None
    categoria_id: Optional[int] = None
    ingredientes_json: Optional[str] = None
    extras_json: Optional[str] = None
    media_json: Optional[str] = None
    alergenos: Optional[str] = Field(default=None, max_length=500)
    disponible: Optional[bool] = None
    activo: Optional[bool] = None

class PromocionCreateAdmin(BaseModel):
    titulo: str = Field(min_length=1, max_length=150)
    descripcion: Optional[str] = None
    descuento_pct: Optional[float] = Field(default=0.0, ge=0, le=100, allow_inf_nan=False)
    precio_global: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)
    codigo_cupon: Optional[str] = None
    banner_url: Optional[str] = None
    activo: Optional[bool] = True
    dias_semana: Optional[str] = Field(default=None, max_length=40)
    hora_inicio: Optional[str] = Field(default=None, max_length=5)
    hora_fin: Optional[str] = Field(default=None, max_length=5)
    producto_ids: List[int] = Field(default_factory=list)

    @field_validator("hora_inicio", "hora_fin", "dias_semana", mode="before")
    @classmethod
    def _empty_schedule_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value


class PromocionProductosUpdate(BaseModel):
    producto_ids: List[int] = Field(default_factory=list)

class ResenaCreateAdmin(BaseModel):
    nombre_cliente: str
    comentario: str
    estrellas: Optional[int] = 5
    foto_url: Optional[str] = None

class PublicacionCreateAdmin(BaseModel):
    titulo: str
    contenido: str
    imagen_url: Optional[str] = None
    autor: Optional[str] = "Donde David"
    activo: Optional[bool] = True

class GuiaItemCreate(BaseModel):
    titulo: str
    descripcion: Optional[str] = None
    media_url: str
    tipo_media: Optional[str] = "imagen"
    tipo_vista: Optional[str] = "ambos"
    orden: Optional[int] = 1

class ConfiguracionUpdate(BaseModel):
    clave: str = Field(min_length=1, max_length=100)
    valor: str = Field(max_length=1000)


def validate_product_json(value: Optional[str], field: str) -> None:
    if value is None:
        return
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail=f"{field} debe contener JSON válido.") from exc
    if not isinstance(parsed, list) or len(parsed) > 30:
        raise HTTPException(status_code=422, detail=f"{field} debe ser una lista de hasta 30 elementos.")
    if field == "extras_json":
        names = set()
        for item in parsed:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("nombre"), str)
                or not item["nombre"].strip()
                or len(item["nombre"]) > 100
                or isinstance(item.get("precio"), bool)
                or not isinstance(item.get("precio"), (int, float))
                or not math.isfinite(item["precio"])
                or item["precio"] < 0
                or item["precio"] > 100000
            ):
                raise HTTPException(status_code=422, detail="Cada extra requiere nombre y precio válido.")
            normalized_name = item["nombre"].strip().casefold()
            if normalized_name in names:
                raise HTTPException(status_code=422, detail="No se permiten extras duplicados en un producto.")
            names.add(normalized_name)
    elif field == "media_json":
        for item in parsed:
            if (
                not isinstance(item, dict)
                or item.get("tipo") not in {"imagen", "video"}
                or not isinstance(item.get("url"), str)
                or not item["url"].strip()
                or len(item["url"]) > 500
            ):
                raise HTTPException(status_code=422, detail="Cada contenido multimedia requiere tipo y URL.")
            media_url = item["url"].strip()
            parsed_url = urlsplit(media_url)
            if not (
                (parsed_url.scheme == "https" and parsed_url.netloc and not parsed_url.username and not parsed_url.password)
                or media_url.startswith("/static/uploads/")
            ):
                raise HTTPException(
                    status_code=422,
                    detail="La URL multimedia debe usar HTTPS o una ruta local /static/uploads/.",
                )


class ConfiguracionBatchUpdate(BaseModel):
    configuraciones: List[ConfiguracionUpdate] = Field(min_length=1, max_length=30)


def validate_configuracion(data: ConfiguracionUpdate) -> None:
    public_text_limits = {
        "nombre_restaurante": 80,
        "historia_restaurante": 300,
        "direccion_restaurante": 160,
        "footer_enlaces_titulo": 48,
        "footer_inicio_texto": 40,
        "footer_menu_texto": 48,
        "footer_puntos_texto": 48,
        "footer_atencion_titulo": 48,
        "horario_atencion": 120,
        "servicio_restaurante": 120,
        "medios_pago_texto": 140,
        "landing_titulo": 100,
        "landing_descripcion": 300,
    }
    max_length = public_text_limits.get(data.clave)
    if max_length is not None:
        if not data.valor.strip():
            raise HTTPException(status_code=422, detail=f"El valor de {data.clave} no puede estar vacío.")
        if len(data.valor.strip()) > max_length:
            raise HTTPException(
                status_code=422,
                detail=f"El valor de {data.clave} no puede superar {max_length} caracteres.",
            )

    if data.clave == "iva_activo":
        if str(data.valor).lower() not in {"true", "false", "1", "0"}:
            raise HTTPException(status_code=422, detail="El valor de iva_activo debe ser 'true' o 'false'.")

    numeric_limits = {
        "impuesto_porcentaje": (0.0, 100.0),
        "costo_delivery": (0.0, None),
        "costo_empaque": (0.0, None),
        "tiempo_delivery_estimado_minutos": (1.0, 240.0),
        "tasa_cambio_bs": (0.000001, 999999.0),
    }
    if data.clave in numeric_limits:
        try:
            numeric_value = float(data.valor)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"El valor de {data.clave} debe ser numérico.") from exc
        minimum, maximum = numeric_limits[data.clave]
        if not math.isfinite(numeric_value) or numeric_value < minimum or (maximum is not None and numeric_value > maximum):
            raise HTTPException(status_code=422, detail=f"El valor de {data.clave} está fuera del rango permitido.")


def set_configuracion(db: Session, data: ConfiguracionUpdate) -> None:
    config = db.query(Configuracion).filter(Configuracion.clave == data.clave).first()
    if config is None:
        db.add(Configuracion(clave=data.clave, valor=data.valor))
    else:
        config.valor = data.valor


@router.post("/tasa-bcv/actualizar")
def actualizar_tasa_bcv(db: Session = Depends(get_db)):
    rate = get_bcv_rate(db, force_refresh=True)
    if rate["tasa_cambio_bs"] is None or rate["tasa_estado"] != "actualizada":
        raise HTTPException(status_code=503, detail="No se pudo validar una tasa BCV reciente. Se conserva la última tasa guardada.")
    return rate

# ==================== UPLOAD ARCHIVOS LOCALES EN SERVIDOR ====================
UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../static/uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    extension = os.path.splitext(file.filename or "")[1].lower()
    supported_types = {
        ".jpg": ("image/jpeg", lambda content: content.startswith(b"\xff\xd8\xff")),
        ".jpeg": ("image/jpeg", lambda content: content.startswith(b"\xff\xd8\xff")),
        ".png": ("image/png", lambda content: content.startswith(b"\x89PNG\r\n\x1a\n")),
        ".webp": ("image/webp", lambda content: content.startswith(b"RIFF") and content[8:12] == b"WEBP"),
    }
    file_type = supported_types.get(extension)
    if not file_type or file.content_type != file_type[0]:
        raise HTTPException(status_code=415, detail="Solo se permiten imágenes JPEG, PNG o WEBP válidas.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El archivo supera el límite de 5 MB.")
    if not file_type[1](content):
        raise HTTPException(status_code=415, detail="El contenido del archivo no coincide con una imagen válida.")

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    cloud_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
    cloud_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    if cloud_name and cloud_key and cloud_secret:
        ts = str(int(datetime.now(timezone.utc).timestamp()))
        folder = os.getenv("CLOUDINARY_FOLDER", "donde_david").strip()
        sig_payload = f"folder={folder}&timestamp={ts}{cloud_secret}"
        signature = hashlib.sha1(sig_payload.encode("utf-8")).hexdigest()
        upload_endpoint = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    upload_endpoint,
                    data={"api_key": cloud_key, "timestamp": ts, "folder": folder, "signature": signature},
                    files={"file": (file.filename or f"upload{extension}", content, file.content_type)},
                )
            if resp.status_code == 200:
                cloud_data = resp.json()
                secure_url = cloud_data.get("secure_url")
                if secure_url:
                    return {"url": secure_url, "filename": cloud_data.get("public_id", ""), "provider": "cloudinary"}
        except Exception as exc:
            logger.warning("Cloudinary upload fallback to local storage: %s", exc)

    unique_filename = f"{uuid.uuid4().hex}{extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=UPLOAD_DIR, delete=False) as temporary_file:
            temporary_path = temporary_file.name
            temporary_file.write(content)
        os.replace(temporary_path, file_path)
        relative_url = f"/static/uploads/{unique_filename}"
        return {"url": relative_url, "filename": unique_filename}
    except OSError as exc:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)
        logger.exception("Failed to store uploaded image.")
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo.") from exc

# ==================== DASHBOARD & METRICS ====================
def _resolve_metric_category_ids(db: Session, categoria: Optional[str]) -> Optional[list[int]]:
    if not categoria:
        return None
    norm = categoria.strip().lower()
    if not norm or norm == "todas":
        return None
    all_cats = db.query(Categoria).all()
    postre_terms = ("postre", "dulce", "helado")
    bebida_terms = ("bebida", "refresco", "malteada", "jugo")
    if norm == "postres":
        return [c.id for c in all_cats if any(t in (c.nombre or "").lower() for t in postre_terms)]
    if norm == "bebidas":
        return [c.id for c in all_cats if any(t in (c.nombre or "").lower() for t in bebida_terms)]
    if norm == "comidas":
        excluded = postre_terms + bebida_terms + ("extra",)
        return [c.id for c in all_cats if not any(t in (c.nombre or "").lower() for t in excluded)]
    return [c.id for c in all_cats if (c.nombre or "").strip().lower() == norm or str(c.id) == norm]


def _apply_metric_payment_filter(query, metodo_pago: Optional[str]):
    if not metodo_pago:
        return query
    norm = metodo_pago.strip().lower()
    if not norm or norm == "todos":
        return query
    if norm in ("efectivo", "cash"):
        return query.filter(func.lower(Pedido.metodo_pago).in_(["efectivo", "cash"]))
    if "movil" in norm or "móvil" in norm:
        return query.filter(func.lower(Pedido.metodo_pago).in_(["pago móvil", "pago movil", "transferencia"]))
    if "tarjeta" in norm or "punto" in norm:
        return query.filter(func.lower(Pedido.metodo_pago).in_(["punto de venta", "tarjeta"]))
    if "divisa" in norm or "usd" in norm:
        return query.filter(
            Pedido.moneda_pago == "USD",
            func.lower(Pedido.metodo_pago).in_(["efectivo", "cash", "divisas"]),
        )
    return query.filter(func.lower(Pedido.metodo_pago) == norm)


@router.get("/dashboard-stats")
def get_dashboard_stats(
    categoria: Optional[str] = Query(None),
    metodo_pago: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor"]))
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    previous_week_start = week_start - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_month_start = (month_start - timedelta(days=1)).replace(day=1)

    cat_ids = _resolve_metric_category_ids(db, categoria)
    active_category_filter = (categoria or "todas").strip().lower() or "todas"
    active_payment_filter = (metodo_pago or "todos").strip() or "todos"

    def sales_between(start: Optional[datetime], end: Optional[datetime]) -> float:
        if cat_ids is not None:
            if not cat_ids:
                return 0.0
            query = (
                db.query(func.sum(DetallePedido.subtotal))
                .join(Pedido, Pedido.id == DetallePedido.pedido_id)
                .join(Producto, Producto.id == DetallePedido.producto_id)
                .filter(
                    Pedido.estado_pago == "PAGADO",
                    Producto.categoria_id.in_(cat_ids),
                )
            )
        else:
            query = db.query(func.sum(Pedido.total)).filter(Pedido.estado_pago == "PAGADO")
        query = _apply_metric_payment_filter(query, metodo_pago)
        if start is not None:
            query = query.filter(func.coalesce(Pedido.fecha_pago, Pedido.fecha_creacion) >= start)
        if end is not None:
            query = query.filter(func.coalesce(Pedido.fecha_pago, Pedido.fecha_creacion) < end)
        return float(query.scalar() or 0.0)

    def growth(current: float, previous: float) -> str:
        if previous == 0:
            return "N/D"
        return f"{((current - previous) / previous) * 100:+.1f}%"

    total_usuarios = db.query(Usuario).filter(Usuario.activo == True).count()
    total_productos = db.query(Producto).filter(Producto.activo == True).count()

    filtered_orders_query = _apply_metric_payment_filter(db.query(Pedido), metodo_pago)
    if cat_ids is not None:
        if not cat_ids:
            total_pedidos = 0
        else:
            count_q = (
                db.query(func.count(func.distinct(Pedido.id)))
                .join(DetallePedido, Pedido.id == DetallePedido.pedido_id)
                .join(Producto, Producto.id == DetallePedido.producto_id)
                .filter(Producto.categoria_id.in_(cat_ids))
            )
            total_pedidos = int(_apply_metric_payment_filter(count_q, metodo_pago).scalar() or 0)
    else:
        total_pedidos = filtered_orders_query.count()

    total_ventas = sales_between(None, None)
    ventas_hoy = sales_between(today_start, now + timedelta(microseconds=1))
    ventas_semana = sales_between(week_start, now + timedelta(microseconds=1))
    ventas_semana_anterior = sales_between(previous_week_start, week_start)
    ventas_mes = sales_between(month_start, now + timedelta(microseconds=1))
    ventas_mes_anterior = sales_between(previous_month_start, month_start)

    caja_efectivo = db.query(Turno).filter(Turno.activo == True).first()
    monto_caja = float(caja_efectivo.monto_apertura or 0) if caja_efectivo else 0.0
    if caja_efectivo:
        cash_sales = db.query(func.coalesce(func.sum(Pedido.total), 0)).filter(
            Pedido.turno_id == caja_efectivo.id,
            Pedido.estado_pago == "PAGADO",
            func.lower(Pedido.metodo_pago).in_(["efectivo", "cash"]),
        ).scalar()
        cash_expenses = db.query(func.coalesce(func.sum(MovimientoCaja.monto_usd), 0)).filter(
            MovimientoCaja.turno_id == caja_efectivo.id,
            MovimientoCaja.tipo == "EGRESO",
            func.lower(MovimientoCaja.metodo_pago) == "efectivo",
        ).scalar()
        monto_caja = round(monto_caja + float(cash_sales or 0) - float(cash_expenses or 0), 2)

    stock_critico_count = db.query(Insumo).filter(Insumo.estado == "CRITICO").count()
    pedidos_cocina_count = db.query(Pedido).filter(Pedido.estado.in_(["PENDIENTE", "EN_PREPARACION"])).count()
    delivery_count = db.query(Pedido).filter(Pedido.tipo == "delivery").count()
    mesas_ocupadas_count = db.query(Mesa).filter(Mesa.estado == "OCUPADA").count()

    if cat_ids is not None and not cat_ids:
        top_productos = []
    else:
        top_query = (
            db.query(
                Producto.nombre,
                func.sum(DetallePedido.cantidad).label("unidades"),
                func.sum(DetallePedido.subtotal).label("total_ingresos")
            )
            .join(DetallePedido, Producto.id == DetallePedido.producto_id)
            .join(Pedido, Pedido.id == DetallePedido.pedido_id)
            .filter(Pedido.estado_pago == "PAGADO")
        )
        if cat_ids is not None:
            top_query = top_query.filter(Producto.categoria_id.in_(cat_ids))
        top_query = _apply_metric_payment_filter(top_query, metodo_pago)
        top_productos = (
            top_query.group_by(Producto.id, Producto.nombre)
            .order_by(func.sum(DetallePedido.cantidad).desc())
            .limit(5)
            .all()
        )

    top_list = [
        {"nombre": name, "unidades": int(units), "total": float(tot)}
        for name, units, tot in top_productos
    ] if top_productos else []

    def count_channel(channel_name: str) -> int:
        if cat_ids is not None and not cat_ids:
            return 0
        q = db.query(func.count(func.distinct(Pedido.id))).filter(
            Pedido.tipo == channel_name,
            Pedido.estado_pago == "PAGADO",
        )
        if cat_ids is not None:
            q = q.join(DetallePedido, Pedido.id == DetallePedido.pedido_id).join(
                Producto, Producto.id == DetallePedido.producto_id
            ).filter(Producto.categoria_id.in_(cat_ids))
        q = _apply_metric_payment_filter(q, metodo_pago)
        return int(q.scalar() or 0)

    count_mesa = count_channel("mesa")
    count_delivery = count_channel("delivery")
    count_llevar = count_channel("llevar")
    total_canales = count_mesa + count_delivery + count_llevar

    pct_mesa = int(round((count_mesa / total_canales) * 100)) if total_canales else 0
    pct_delivery = int(round((count_delivery / total_canales) * 100)) if total_canales else 0
    pct_llevar = 100 - pct_mesa - pct_delivery if total_canales else 0
    total_mesas = db.query(Mesa).count()

    return {
        "total_usuarios": total_usuarios,
        "total_productos": total_productos,
        "total_pedidos": total_pedidos,
        "total_ventas": round(total_ventas, 2),
        "ventas_hoy": round(ventas_hoy, 2),
        "ventas_semana": round(ventas_semana, 2),
        "ventas_mes": round(ventas_mes, 2),
        "pct_crecimiento_semanal": growth(ventas_semana, ventas_semana_anterior),
        "pct_crecimiento_mensual": growth(ventas_mes, ventas_mes_anterior),
        "desglose_canales": {
            "pct_mesa": pct_mesa,
            "pct_delivery": pct_delivery,
            "pct_llevar": pct_llevar,
            "total_pedidos_pagados": total_canales,
        },
        "monto_caja": monto_caja,
        "stock_critico": stock_critico_count,
        "pedidos_cocina": pedidos_cocina_count,
        "delivery_pedidos": delivery_count,
        "mesas_ocupadas": mesas_ocupadas_count,
        "total_mesas": total_mesas,
        "top_productos": top_list,
        "filtros_aplicados": {
            "categoria": active_category_filter,
            "metodo_pago": active_payment_filter,
        },
    }

# ==================== TOUR BIENVENIDA ONBOARDING ====================
@router.post("/tour-completed")
def mark_tour_completed(db: Session = Depends(get_db), current_user = Depends(require_roles(["admin", "supervisor"]))):
    user = db.query(Usuario).filter(Usuario.id == current_user.id).first()
    if user:
        user.tour_completed = True
        db.commit()
    return {"tour_completed": True, "mensaje": "Tour de bienvenida completado y registrado"}

# ==================== PUBLICACIONES / ANUNCIOS CRUD ====================
@router.get("/publicaciones")
def list_publicaciones_admin(db: Session = Depends(get_db)):
    return db.query(Publicacion).order_by(Publicacion.fecha_creacion.desc()).all()

@router.post("/publicaciones")
def create_publicacion_admin(data: PublicacionCreateAdmin, db: Session = Depends(get_db)):
    nueva = Publicacion(
        titulo=data.titulo,
        contenido=data.contenido,
        imagen_url=data.imagen_url,
        autor=data.autor or "Donde David",
        activo=data.activo if data.activo is not None else True
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva

@router.delete("/publicaciones/{pub_id}")
def delete_publicacion_admin(pub_id: int, db: Session = Depends(get_db)):
    p = db.query(Publicacion).filter(Publicacion.id == pub_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    db.delete(p)
    db.commit()
    return {"mensaje": "Publicación eliminada correctamente"}

# ==================== PROMOCIONES CRUD (BOOM! PROMO DEL DIA) ====================
def _resolve_promo_products(db: Session, producto_ids: List[int]) -> List[Producto]:
    unique_ids: List[int] = []
    for pid in producto_ids:
        if pid not in unique_ids:
            unique_ids.append(pid)
    if not unique_ids:
        return []
    found = db.query(Producto).filter(Producto.id.in_(unique_ids)).all()
    by_id = {prod.id: prod for prod in found}
    missing = [pid for pid in unique_ids if pid not in by_id]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Productos no encontrados para la promoción: {missing}",
        )
    return [by_id[pid] for pid in unique_ids]


def _serialize_promocion(promo: Promocion) -> dict:
    linked = [
        {
            "id": prod.id,
            "nombre": prod.nombre,
            "descripcion": prod.descripcion,
            "precio": float(prod.precio or 0),
            "precio_promocion": float(prod.precio_promocion) if prod.precio_promocion is not None else None,
            "imagen_url": prod.imagen_url,
            "categoria_id": prod.categoria_id,
            "disponible": bool(prod.disponible),
            "activo": bool(prod.activo),
            "stock": int(prod.stock or 0),
            "puntos_fidelidad": int(prod.puntos_fidelidad or 0),
            "tiempo_preparacion": int(prod.tiempo_preparacion or 15),
        }
        for prod in (promo.productos or [])
    ]
    return {
        "id": promo.id,
        "titulo": promo.titulo,
        "descripcion": promo.descripcion,
        "descuento_pct": float(promo.descuento_pct or 0.0),
        "precio_global": float(promo.precio_global) if promo.precio_global is not None else None,
        "codigo_cupon": promo.codigo_cupon,
        "banner_url": promo.banner_url,
        "activo": bool(promo.activo),
        "fecha_inicio": promo.fecha_inicio.isoformat() if promo.fecha_inicio else None,
        "fecha_fin": promo.fecha_fin.isoformat() if promo.fecha_fin else None,
        "dias_semana": promo.dias_semana,
        "hora_inicio": promo.hora_inicio,
        "hora_fin": promo.hora_fin,
        "producto_ids": [item["id"] for item in linked],
        "productos": linked,
    }


@router.get("/promociones")
def list_promociones(db: Session = Depends(get_db)):
    promos = db.query(Promocion).order_by(Promocion.id.asc()).all()
    return [_serialize_promocion(promo) for promo in promos]


@router.post("/promociones")
async def create_promocion(data: PromocionCreateAdmin, db: Session = Depends(get_db)):
    selected_products = _resolve_promo_products(db, data.producto_ids)
    nueva = Promocion(
        titulo=data.titulo,
        descripcion=data.descripcion,
        descuento_pct=data.descuento_pct or 0.0,
        precio_global=round(float(data.precio_global), 2) if data.precio_global is not None else None,
        codigo_cupon=data.codigo_cupon or None,
        banner_url=data.banner_url,
        activo=data.activo if data.activo is not None else True,
        dias_semana=data.dias_semana,
        hora_inicio=data.hora_inicio,
        hora_fin=data.hora_fin,
        productos=selected_products,
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    payload = _serialize_promocion(nueva)
    await ws_manager.broadcast("PROMOCIONES_ACTUALIZADAS", {
        "accion": "CREAR",
        "promocion_id": nueva.id,
        "titulo": nueva.titulo,
        "activo": bool(nueva.activo),
        "descuento_pct": float(nueva.descuento_pct or 0.0),
        "precio_global": payload["precio_global"],
        "productos_count": len(payload["producto_ids"]),
    })
    return payload


@router.put("/promociones/{promo_id}")
async def update_promocion(promo_id: int, data: PromocionCreateAdmin, db: Session = Depends(get_db)):
    p = db.query(Promocion).filter(Promocion.id == promo_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Promoción no encontrada")

    selected_products = _resolve_promo_products(db, data.producto_ids)
    p.titulo = data.titulo
    p.descripcion = data.descripcion
    p.descuento_pct = data.descuento_pct or 0.0
    p.precio_global = round(float(data.precio_global), 2) if data.precio_global is not None else None
    p.codigo_cupon = data.codigo_cupon or None
    p.banner_url = data.banner_url
    p.activo = data.activo if data.activo is not None else True
    p.dias_semana = data.dias_semana
    p.hora_inicio = data.hora_inicio
    p.hora_fin = data.hora_fin
    p.productos = selected_products

    db.commit()
    db.refresh(p)
    payload = _serialize_promocion(p)
    await ws_manager.broadcast("PROMOCIONES_ACTUALIZADAS", {
        "accion": "ACTUALIZAR",
        "promocion_id": p.id,
        "titulo": p.titulo,
        "activo": bool(p.activo),
        "descuento_pct": float(p.descuento_pct or 0.0),
        "precio_global": payload["precio_global"],
        "productos_count": len(payload["producto_ids"]),
    })
    return payload


@router.put("/promociones/{promo_id}/productos")
async def update_promocion_productos(
    promo_id: int,
    data: PromocionProductosUpdate,
    db: Session = Depends(get_db),
):
    p = db.query(Promocion).filter(Promocion.id == promo_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Promoción no encontrada")
    p.productos = _resolve_promo_products(db, data.producto_ids)
    db.commit()
    db.refresh(p)
    payload = _serialize_promocion(p)
    await ws_manager.broadcast("PROMOCIONES_ACTUALIZADAS", {
        "accion": "ACTUALIZAR_PRODUCTOS",
        "promocion_id": p.id,
        "titulo": p.titulo,
        "activo": bool(p.activo),
        "productos_count": len(payload["producto_ids"]),
    })
    return payload


@router.delete("/promociones/{promo_id}")
async def delete_promocion(promo_id: int, db: Session = Depends(get_db)):
    p = db.query(Promocion).filter(Promocion.id == promo_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Promoción no encontrada")
    db.delete(p)
    db.commit()
    await ws_manager.broadcast("PROMOCIONES_ACTUALIZADAS", {
        "accion": "ELIMINAR",
        "promocion_id": promo_id,
    })
    return {"mensaje": "Promoción eliminada"}

# ==================== RESEÑAS / TESTIMONIOS ====================
@router.get("/resenas")
def list_resenas_admin(db: Session = Depends(get_db)):
    return db.query(Resena).order_by(Resena.fecha_creacion.desc()).all()

@router.post("/resenas")
def create_resena_admin(data: ResenaCreateAdmin, db: Session = Depends(get_db)):
    nueva = Resena(
        nombre_cliente=data.nombre_cliente,
        comentario=data.comentario,
        estrellas=data.estrellas or 5,
        foto_url=data.foto_url
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva

@router.delete("/resenas/{resena_id}")
def delete_resena_admin(resena_id: int, db: Session = Depends(get_db)):
    r = db.query(Resena).filter(Resena.id == resena_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Reseña no encontrada")
    db.delete(r)
    db.commit()
    return {"mensaje": "Reseña eliminada"}

# ==================== GUÍA & CARRUSEL INTERACTIVO ADMIN ====================
@router.get("/guia")
def list_guia_admin(db: Session = Depends(get_db)):
    return db.query(GuiaItem).order_by(GuiaItem.orden.asc()).all()

@router.post("/guia")
def create_guia_admin(data: GuiaItemCreate, db: Session = Depends(get_db)):
    nuevo = GuiaItem(
        titulo=data.titulo,
        descripcion=data.descripcion,
        media_url=data.media_url,
        tipo_media=data.tipo_media or "imagen",
        tipo_vista=data.tipo_vista or "ambos",
        orden=data.orden or 1
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.delete("/guia/{item_id}")
def delete_guia_admin(item_id: int, db: Session = Depends(get_db)):
    item = db.query(GuiaItem).filter(GuiaItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Elemento de guía no encontrado")
    db.delete(item)
    db.commit()
    return {"mensaje": "Elemento de la guía eliminado correctamente"}

# ==================== MESAS DYNAMIC ABM ====================
@router.get("/mesas")
def get_mesas(db: Session = Depends(get_db)):
    return db.query(Mesa).order_by(Mesa.numero_mesa.asc()).all()

@router.post("/mesas")
def create_mesa(data: MesaCreate, db: Session = Depends(get_db)):
    if db.query(Mesa).filter(Mesa.numero_mesa == data.numero_mesa).first():
        raise HTTPException(status_code=400, detail=f"La Mesa #{data.numero_mesa} ya existe.")
    
    nueva = Mesa(
        numero_mesa=data.numero_mesa,
        capacidad=data.capacidad,
        zona=(data.zona or "Salón").strip() or "Salón",
        estado="LIBRE",
        codigo_qr=f"QR_DONDE_DAVID_MESA_{data.numero_mesa}"
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return nueva


@router.put("/mesas/{numero_mesa}")
def update_mesa(numero_mesa: int, data: MesaUpdate, db: Session = Depends(get_db)):
    mesa = db.query(Mesa).filter(Mesa.numero_mesa == numero_mesa).first()
    if not mesa:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    if data.capacidad is not None:
        mesa.capacidad = data.capacidad
    if data.zona is not None:
        mesa.zona = data.zona.strip() or "Salón"
    db.commit()
    db.refresh(mesa)
    return mesa

@router.delete("/mesas/{numero_mesa}")
def delete_mesa(numero_mesa: int, db: Session = Depends(get_db)):
    mesa = db.query(Mesa).filter(Mesa.numero_mesa == numero_mesa).first()
    if not mesa:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    db.delete(mesa)
    db.commit()
    return {"mensaje": f"Mesa #{numero_mesa} eliminada exitosamente"}

@router.get("/mesas/{numero_mesa}/qr")
def get_qr_mesa(numero_mesa: int, request: Request, db: Session = Depends(get_db)):
    mesa = db.query(Mesa).filter(Mesa.numero_mesa == numero_mesa).first()
    if not mesa:
        raise HTTPException(status_code=404, detail="Mesa no encontrada")
    
    url_acceso = f"{str(request.base_url).rstrip('/')}/static/cliente/app.html?mesa={numero_mesa}"
    qr_svg_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={quote(url_acceso, safe='')}"
    return {
        "numero_mesa": numero_mesa,
        "codigo_qr": mesa.codigo_qr,
        "qr_image_url": qr_svg_url,
        "url_acceso": url_acceso
    }

# ==================== INGRESOS E INSUMOS ====================
@router.post("/ingresos")
def registrar_ingreso(
    data: IngresoCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor"]))
):
    audit = Auditoria(
        accion="Ingreso Extra",
        usuario=current_user.nombre_usuario,
        detalle=f"{data.concepto} - Q{data.monto:.2f}"
    )
    db.add(audit)
    db.commit()
    return {"mensaje": "Ingreso registrado correctamente", "concepto": data.concepto, "monto": data.monto}

@router.get("/insumos")
def get_insumos(db: Session = Depends(get_db)):
    return db.query(Insumo).all()

@router.get("/inventario/movimientos")
def get_inventario_movimientos(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    movimientos = db.query(MovimientoInventario).order_by(
        MovimientoInventario.fecha.desc(),
        MovimientoInventario.id.desc()
    ).offset(offset).limit(limit).all()
    return [
        {
            "id": movimiento.id,
            "producto_id": movimiento.producto_id,
            "producto": movimiento.producto.nombre if movimiento.producto else None,
            "insumo_id": movimiento.insumo_id,
            "insumo": movimiento.insumo.nombre if movimiento.insumo else None,
            "tipo_movimiento": movimiento.tipo_movimiento,
            "cantidad_cambio": float(movimiento.cantidad_cambio),
            "cantidad_anterior": float(movimiento.cantidad_anterior),
            "cantidad_nueva": float(movimiento.cantidad_nueva),
            "motivo": movimiento.motivo,
            "usuario_id": movimiento.usuario_id,
            "usuario": movimiento.usuario.nombre_usuario if movimiento.usuario else None,
            "fecha": movimiento.fecha
        }
        for movimiento in movimientos
    ]

@router.post("/insumos")
def create_insumo(
    data: InsumoCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor"]))
):
    estado = "CRITICO" if data.stock_actual <= data.stock_minimo else "NORMAL"
    nuevo = Insumo(
        nombre=data.nombre,
        stock_actual=data.stock_actual,
        stock_minimo=data.stock_minimo,
        unidad_medida=data.unidad_medida,
        costo_unitario=round(float(data.costo_unitario or 0), 2),
        estado=estado
    )
    db.add(nuevo)
    db.flush()
    if data.stock_actual > 0:
        db.add(MovimientoInventario(
            insumo_id=nuevo.id,
            tipo_movimiento="ENTRADA",
            cantidad_cambio=data.stock_actual,
            cantidad_anterior=0,
            cantidad_nueva=data.stock_actual,
            costo_unitario=round(float(data.costo_unitario or 0), 2),
            motivo="Stock inicial",
            usuario_id=current_user.id
        ))
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.post("/insumos/{insumo_id}/ingreso")
def registrar_ingreso_insumo(
    insumo_id: int,
    data: InsumoIngreso,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor"]))
):
    insumo = db.query(Insumo).filter(Insumo.id == insumo_id).with_for_update().first()
    if not insumo:
        raise HTTPException(status_code=404, detail="Insumo no encontrado")
    
    stock_before = insumo.stock_actual
    insumo.stock_actual += data.cantidad
    if data.costo_unitario is not None:
        insumo.costo_unitario = round(float(data.costo_unitario), 2)
    insumo.estado = "CRITICO" if insumo.stock_actual <= insumo.stock_minimo else "NORMAL"

    db.add_all([
        MovimientoInventario(
            insumo_id=insumo.id,
            tipo_movimiento="ENTRADA",
            cantidad_cambio=data.cantidad,
            cantidad_anterior=stock_before,
            cantidad_nueva=insumo.stock_actual,
            costo_unitario=round(float(data.costo_unitario), 2) if data.costo_unitario is not None else insumo.costo_unitario,
            proveedor=data.proveedor.strip() if data.proveedor else None,
            motivo="Ingreso de inventario",
            usuario_id=current_user.id
        ),
        Auditoria(
            accion="Ingreso Insumo",
            usuario=current_user.nombre_usuario,
            detalle=f"+{data.cantidad} {insumo.unidad_medida} de {insumo.nombre}"
        )
    ])
    db.commit()
    db.refresh(insumo)
    return insumo

# ==================== CATEGORIAS Y PRODUCTOS CRUD ====================
@router.get("/categorias")
def list_categorias_admin(db: Session = Depends(get_db)):
    return db.query(Categoria).order_by(Categoria.orden.asc()).all()

@router.post("/categorias")
def create_categoria_admin(
    data: CategoriaCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    nueva = Categoria(
        nombre=data.nombre,
        descripcion=data.descripcion,
        imagen_url=data.imagen_url or "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500",
        orden=data.orden or 0
    )
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    background_tasks.add_task(ws_manager.broadcast, "PRODUCTOS_ACTUALIZADOS", {})
    return nueva

@router.delete("/categorias/{categoria_id}")
async def delete_categoria_admin(
    categoria_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor"])),
):
    cat = db.query(Categoria).filter(Categoria.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    product_count = db.query(Producto).filter(Producto.categoria_id == categoria_id).count()
    if product_count:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No se puede eliminar «{cat.nombre}»: tiene {product_count} producto(s) asociado(s). "
                "Reasigna primero esos productos a otra categoría; archivarlos no los desvincula."
            ),
        )
    db.delete(cat)
    db.add(Auditoria(
        accion="Eliminación de categoría",
        usuario=current_user.nombre_usuario,
        detalle=f"Categoría #{categoria_id}: {cat.nombre}",
    ))
    db.commit()
    await ws_manager.broadcast("PRODUCTOS_ACTUALIZADOS", {})
    return {"mensaje": "Categoría eliminada"}

@router.get("/productos")
def list_productos_admin(db: Session = Depends(get_db)):
    return db.query(Producto).order_by(Producto.id.desc()).all()

@router.post("/productos")
async def create_producto_admin(data: ProductoCreate, db: Session = Depends(get_db)):
    validate_product_json(data.extras_json, "extras_json")
    validate_product_json(data.media_json, "media_json")
    if not db.query(Categoria).filter(Categoria.id == data.categoria_id).first():
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    if data.precio_promocion is not None and data.precio_promocion > data.precio:
        raise HTTPException(
            status_code=422,
            detail="El precio promocional no puede ser mayor al precio base.",
        )
    nuevo = Producto(
        nombre=data.nombre,
        descripcion=data.descripcion,
        precio=data.precio,
        precio_promocion=data.precio_promocion,
        costo_unitario=round(float(data.costo_unitario or 0), 2),
        categoria_id=data.categoria_id,
        imagen_url=data.imagen_url or "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=500",
        stock=data.stock if data.stock is not None else 50,
        puntos_fidelidad=data.puntos_fidelidad,
        tiempo_preparacion=data.tiempo_preparacion,
        ingredientes_json=data.ingredientes_json,
        extras_json=data.extras_json,
        media_json=data.media_json,
        alergenos=data.alergenos,
        disponible=data.disponible,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    await ws_manager.broadcast("PRODUCTOS_ACTUALIZADOS", {"producto_id": nuevo.id, "nombre": nuevo.nombre})
    return nuevo

@router.put("/productos/{producto_id}")
async def update_producto_admin(
    producto_id: int,
    data: ProductoUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor"]))
):
    p = db.query(Producto).filter(Producto.id == producto_id).with_for_update().first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    validate_product_json(data.extras_json, "extras_json")
    validate_product_json(data.media_json, "media_json")
    if data.categoria_id is not None and not db.query(Categoria).filter(Categoria.id == data.categoria_id).first():
        raise HTTPException(status_code=404, detail="Categoría no encontrada")

    effective_price = data.precio if data.precio is not None else p.precio
    effective_promo = (
        data.precio_promocion if "precio_promocion" in data.model_fields_set else p.precio_promocion
    )
    if effective_promo is not None and effective_price is not None and float(effective_promo) > float(effective_price):
        raise HTTPException(
            status_code=422,
            detail="El precio promocional no puede ser mayor al precio base.",
        )
    
    if data.nombre is not None: p.nombre = data.nombre
    if data.descripcion is not None: p.descripcion = data.descripcion
    if data.precio is not None: p.precio = data.precio
    if "precio_promocion" in data.model_fields_set: p.precio_promocion = data.precio_promocion
    if data.costo_unitario is not None: p.costo_unitario = round(float(data.costo_unitario), 2)
    if data.stock is not None:
        stock_before = int(p.stock or 0)
        p.stock = data.stock
        if data.stock != stock_before:
            db.add(MovimientoInventario(
                producto_id=p.id,
                tipo_movimiento="AJUSTE",
                cantidad_cambio=data.stock - stock_before,
                cantidad_anterior=stock_before,
                cantidad_nueva=data.stock,
                motivo="Ajuste manual de stock",
                usuario_id=current_user.id
            ))
    if data.puntos_fidelidad is not None: p.puntos_fidelidad = data.puntos_fidelidad
    if data.tiempo_preparacion is not None: p.tiempo_preparacion = data.tiempo_preparacion
    if data.imagen_url is not None: p.imagen_url = data.imagen_url
    if data.categoria_id is not None: p.categoria_id = data.categoria_id
    if data.ingredientes_json is not None: p.ingredientes_json = data.ingredientes_json
    if data.extras_json is not None: p.extras_json = data.extras_json
    if data.media_json is not None: p.media_json = data.media_json
    if "alergenos" in data.model_fields_set: p.alergenos = data.alergenos
    if data.disponible is not None: p.disponible = data.disponible
    if data.activo is not None: p.activo = data.activo

    db.commit()
    db.refresh(p)
    await ws_manager.broadcast("PRODUCTOS_ACTUALIZADOS", {"producto_id": p.id, "nombre": p.nombre})
    return p

@router.delete("/productos/{producto_id}")
async def delete_producto_admin(
    producto_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor"])),
):
    prod = db.query(Producto).filter(Producto.id == producto_id).with_for_update().first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if not prod.activo:
        return {"mensaje": "El producto ya estaba archivado.", "producto_id": prod.id, "activo": False}
    prod.activo = False
    db.add(Auditoria(
        accion="Archivo de producto",
        usuario=current_user.nombre_usuario,
        detalle=f"Producto #{prod.id}: {prod.nombre}",
    ))
    db.commit()
    await ws_manager.broadcast("PRODUCTOS_ACTUALIZADOS", {"producto_id": producto_id})
    return {
        "mensaje": "Producto archivado; se conserva en el historial y en los pedidos anteriores.",
        "producto_id": prod.id,
        "activo": False,
    }

# ==================== CONFIGURACIONES GLOBALES (HISTORIA & REDES) ====================
@router.post("/configuraciones")
async def update_configuracion_admin(
    data: ConfiguracionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor"])),
):
    validate_configuracion(data)
    set_configuracion(db, data)
    if data.clave == "tasa_cambio_bs":
        source = db.query(Configuracion).filter(Configuracion.clave == "tasa_fuente").first()
        updated_at = db.query(Configuracion).filter(Configuracion.clave == "tasa_actualizada_at").first()
        timestamp = datetime.now(timezone.utc).isoformat()
        if source is None:
            db.add(Configuracion(clave="tasa_fuente", valor="Manual (administrador)"))
        else:
            source.valor = "Manual (administrador)"
        if updated_at is None:
            db.add(Configuracion(clave="tasa_actualizada_at", valor=timestamp))
        else:
            updated_at.valor = timestamp
    record_audit(
        db=db,
        accion="CONFIG_UPDATE",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="configuraciones",
        recurso_id=data.clave,
        detalle=f"Configuración '{data.clave}' actualizada",
        datos_nuevos={"clave": data.clave, "valor": data.valor},
        auto_commit=False,
    )
    db.commit()
    await ws_manager.broadcast("CONFIGURACION_ACTUALIZADA", {"clave": data.clave, "valor": data.valor})
    return {"clave": data.clave, "valor": data.valor}


@router.post("/configuraciones/lote")
async def update_configuraciones_batch(
    data: ConfiguracionBatchUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor"])),
):
    keys = [item.clave for item in data.configuraciones]
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=422, detail="No se permiten claves duplicadas en el mismo guardado.")
    for item in data.configuraciones:
        validate_configuracion(item)
    for item in data.configuraciones:
        set_configuracion(db, item)
    rate = next((item for item in data.configuraciones if item.clave == "tasa_cambio_bs"), None)
    if rate:
        set_configuracion(db, ConfiguracionUpdate(clave="tasa_fuente", valor="Manual (administrador)"))
        set_configuracion(db, ConfiguracionUpdate(
            clave="tasa_actualizada_at",
            valor=datetime.now(timezone.utc).isoformat(),
        ))
    record_audit(
        db=db,
        accion="CONFIG_BATCH_UPDATE",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="configuraciones",
        detalle=f"Actualización en lote de {len(keys)} configuraciones",
        datos_nuevos={"claves": keys},
        auto_commit=False,
    )
    db.commit()
    await ws_manager.broadcast("CONFIGURACION_ACTUALIZADA", {"claves": keys})
    return {"guardadas": keys}

# ==================== GESTIÓN DE USUARIOS DEL SISTEMA ====================
class UsuarioCreateAdmin(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    email: EmailStr
    telefono: Optional[str] = None
    nombre_usuario: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=12, max_length=72)
    rol: Literal["admin", "supervisor", "gerente", "caja", "cocina", "cliente", "mesero", "repartidor"] = "mesero"
    activo: Optional[bool] = True

class UsuarioUpdateAdmin(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    email: Optional[EmailStr] = None
    telefono: Optional[str] = None
    rol: Optional[Literal["admin", "supervisor", "gerente", "caja", "cocina", "cliente", "mesero", "repartidor"]] = None
    password: Optional[str] = Field(default=None, min_length=12, max_length=72)
    activo: Optional[bool] = None

@router.get("/usuarios")
def list_usuarios(
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor"]))
):
    return db.query(Usuario).order_by(Usuario.id.desc()).all()

@router.post("/usuarios")
def create_usuario_admin(
    data: UsuarioCreateAdmin,
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor"]))
):
    if data.rol == "admin" and user.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo un administrador puede crear otra cuenta admin.")
    if db.query(Usuario).filter(Usuario.nombre_usuario == data.nombre_usuario).first():
        raise HTTPException(status_code=400, detail=f"El nombre de usuario '{data.nombre_usuario}' ya existe.")
    if db.query(Usuario).filter(Usuario.email == data.email).first():
        raise HTTPException(status_code=400, detail=f"El correo '{data.email}' ya está registrado.")
    
    nuevo = Usuario(
        nombre=data.nombre,
        apellido=data.apellido,
        email=data.email,
        telefono=data.telefono,
        nombre_usuario=data.nombre_usuario,
        contraseña_hash=get_password_hash(data.password),
        rol=data.rol,
        activo=data.activo if data.activo is not None else True
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    record_audit(
        db=db,
        accion="USER_CREATE",
        usuario=user.nombre_usuario,
        usuario_id=user.id,
        recurso="usuarios",
        recurso_id=str(nuevo.id),
        detalle=f"Usuario '{nuevo.nombre_usuario}' creado con rol '{nuevo.rol}'",
        datos_nuevos={"id": nuevo.id, "nombre_usuario": nuevo.nombre_usuario, "rol": nuevo.rol, "email": nuevo.email}
    )
    return nuevo

@router.put("/usuarios/{usuario_id}")
def update_usuario_admin(
    usuario_id: int,
    data: UsuarioUpdateAdmin,
    db: Session = Depends(get_db),
    user = Depends(require_roles(["admin", "supervisor"]))
):
    u = db.query(Usuario).filter(Usuario.id == usuario_id).with_for_update().first()
    if not u:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if data.rol == "admin" and user.rol != "admin":
        raise HTTPException(status_code=403, detail="Solo un administrador puede asignar el rol admin.")
    if u.id == user.id and data.activo is False:
        raise HTTPException(status_code=409, detail="No puedes desactivar tu propia cuenta mientras estás autenticado.")

    removing_admin = (
        u.rol == "admin"
        and u.activo
        and ((data.rol is not None and data.rol != "admin") or data.activo is False)
    )
    if removing_admin:
        active_admins = db.query(Usuario).filter(Usuario.rol == "admin", Usuario.activo == True).count()
        if active_admins <= 1:
            raise HTTPException(
                status_code=409,
                detail="Debe existir al menos un administrador activo en el sistema.",
            )

    if data.email is not None and data.email != u.email:
        if db.query(Usuario).filter(Usuario.email == data.email, Usuario.id != u.id).first():
            raise HTTPException(status_code=400, detail=f"El correo '{data.email}' ya está registrado.")

    if data.nombre is not None: u.nombre = data.nombre
    if data.apellido is not None: u.apellido = data.apellido
    if data.email is not None: u.email = data.email
    if data.telefono is not None: u.telefono = data.telefono
    if data.rol is not None: u.rol = data.rol
    if data.activo is not None: u.activo = data.activo
    if data.password and data.password.strip():
        u.contraseña_hash = get_password_hash(data.password)
    
    db.commit()
    db.refresh(u)

    record_audit(
        db=db,
        accion="USER_UPDATE",
        usuario=user.nombre_usuario,
        usuario_id=user.id,
        recurso="usuarios",
        recurso_id=str(u.id),
        detalle=f"Usuario '{u.nombre_usuario}' actualizado",
        datos_nuevos={"id": u.id, "nombre_usuario": u.nombre_usuario, "rol": u.rol, "activo": u.activo}
    )
    return u


# ==================== RECETAS, COMPRAS, STOCK CRÍTICO Y REPORTES ====================
@router.get("/productos/{producto_id}/receta")
def get_producto_receta(producto_id: int, db: Session = Depends(get_db)):
    prod = db.query(Producto).filter(Producto.id == producto_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    rows = db.query(ProductoInsumo).filter(ProductoInsumo.producto_id == producto_id).all()
    return [
        {
            "id": row.id,
            "producto_id": row.producto_id,
            "insumo_id": row.insumo_id,
            "insumo_nombre": row.insumo.nombre if row.insumo else None,
            "unidad_medida": row.insumo.unidad_medida if row.insumo else None,
            "cantidad_por_unidad": float(row.cantidad_por_unidad or 0),
        }
        for row in rows
    ]


@router.put("/productos/{producto_id}/receta")
def update_producto_receta(
    producto_id: int,
    data: RecetaUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor"])),
):
    prod = db.query(Producto).filter(Producto.id == producto_id).with_for_update().first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    seen_insumos = set()
    for item in data.items:
        if item.insumo_id in seen_insumos:
            raise HTTPException(status_code=422, detail="No repitas el mismo insumo en la receta.")
        seen_insumos.add(item.insumo_id)
        if not db.query(Insumo).filter(Insumo.id == item.insumo_id).first():
            raise HTTPException(status_code=404, detail=f"Insumo #{item.insumo_id} no encontrado.")

    db.query(ProductoInsumo).filter(ProductoInsumo.producto_id == producto_id).delete()
    for item in data.items:
        db.add(ProductoInsumo(
            producto_id=producto_id,
            insumo_id=item.insumo_id,
            cantidad_por_unidad=float(item.cantidad_por_unidad),
        ))
    record_audit(
        db=db,
        accion="RECIPE_UPDATE",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="producto_insumos",
        recurso_id=str(producto_id),
        detalle=f"Receta actualizada para '{prod.nombre}' ({len(data.items)} insumos)",
        auto_commit=False,
    )
    db.commit()
    return get_producto_receta(producto_id, db)


@router.post("/inventario/compra")
async def registrar_compra_inventario(
    data: CompraInventarioCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(["admin", "supervisor"])),
):
    if bool(data.insumo_id) == bool(data.producto_id):
        raise HTTPException(status_code=422, detail="Indica exactamente un producto_id o un insumo_id para reabastecer.")

    proveedor_clean = data.proveedor.strip() if data.proveedor else None
    motivo_clean = (data.motivo or "Compra a proveedor").strip()
    costo_clean = round(float(data.costo_unitario), 2)

    if data.insumo_id:
        ins = db.query(Insumo).filter(Insumo.id == data.insumo_id).with_for_update().first()
        if not ins:
            raise HTTPException(status_code=404, detail="Insumo no encontrado.")
        prev = round(float(ins.stock_actual or 0), 4)
        ins.stock_actual = round(prev + float(data.cantidad), 4)
        ins.costo_unitario = costo_clean
        ins.estado = "CRITICO" if ins.stock_actual <= float(ins.stock_minimo or 0) else "NORMAL"
        ins.fecha_actualizacion = datetime.now(timezone.utc)
        mov = MovimientoInventario(
            insumo_id=ins.id,
            tipo_movimiento="ENTRADA",
            cantidad_cambio=data.cantidad,
            cantidad_anterior=prev,
            cantidad_nueva=ins.stock_actual,
            costo_unitario=costo_clean,
            proveedor=proveedor_clean,
            motivo=motivo_clean,
            usuario_id=current_user.id,
        )
        db.add(mov)
        # Re-enable dependent products that have own stock > 0
        dep_ids = [
            row.producto_id
            for row in db.query(ProductoInsumo.producto_id).filter(ProductoInsumo.insumo_id == ins.id).all()
        ]
        if dep_ids and ins.stock_actual > 0:
            db.query(Producto).filter(Producto.id.in_(dep_ids), Producto.stock > 0).update(
                {Producto.disponible: True},
                synchronize_session=False,
            )
        target_name = ins.nombre
        stock_new = ins.stock_actual
    else:
        prod = db.query(Producto).filter(Producto.id == data.producto_id).with_for_update().first()
        if not prod:
            raise HTTPException(status_code=404, detail="Producto no encontrado.")
        qty_int = int(round(data.cantidad))
        if qty_int <= 0:
            raise HTTPException(status_code=422, detail="La cantidad de producto debe ser al menos 1 unidad.")
        prev = int(prod.stock or 0)
        prod.stock = prev + qty_int
        prod.costo_unitario = costo_clean
        if prod.stock > 0:
            prod.disponible = True
        mov = MovimientoInventario(
            producto_id=prod.id,
            tipo_movimiento="ENTRADA",
            cantidad_cambio=qty_int,
            cantidad_anterior=prev,
            cantidad_nueva=prod.stock,
            costo_unitario=costo_clean,
            proveedor=proveedor_clean,
            motivo=motivo_clean,
            usuario_id=current_user.id,
        )
        db.add(mov)
        target_name = prod.nombre
        stock_new = prod.stock

    record_audit(
        db=db,
        accion="INVENTORY_PURCHASE",
        usuario=current_user.nombre_usuario,
        usuario_id=current_user.id,
        recurso="movimientos_inventario",
        recurso_id=str(data.insumo_id or data.producto_id),
        detalle=f"Compra +{data.cantidad} {target_name} (${costo_clean:.2f}/u · {proveedor_clean or 'Sin proveedor'})",
        auto_commit=False,
    )
    db.commit()
    await ws_manager.broadcast("PRODUCTOS_ACTUALIZADOS", {"compra": target_name})
    return {
        "mensaje": f"Reabastecimiento registrado para {target_name}",
        "stock_nuevo": stock_new,
        "costo_unitario": costo_clean,
        "proveedor": proveedor_clean,
    }


@router.get("/stock-alertas")
def get_stock_alertas(db: Session = Depends(get_db)):
    productos_bajos = db.query(Producto).filter(
        Producto.activo == True,
        Producto.stock <= Producto.stock_minimo,
    ).order_by(Producto.stock.asc()).all()
    insumos_bajos = db.query(Insumo).filter(
        (Insumo.estado == "CRITICO") | (Insumo.stock_actual <= Insumo.stock_minimo)
    ).order_by(Insumo.stock_actual.asc()).all()
    return {
        "productos": [
            {"id": p.id, "nombre": p.nombre, "stock": int(p.stock or 0), "stock_minimo": int(p.stock_minimo or 0)}
            for p in productos_bajos
        ],
        "insumos": [
            {
                "id": i.id,
                "nombre": i.nombre,
                "stock_actual": float(i.stock_actual or 0),
                "stock_minimo": float(i.stock_minimo or 0),
                "unidad_medida": i.unidad_medida,
            }
            for i in insumos_bajos
        ],
    }


@router.get("/cocina/sla")
def get_cocina_sla(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
    delivered = db.query(Pedido).filter(
        Pedido.fecha_entrega.isnot(None),
        Pedido.fecha_creacion.isnot(None),
        Pedido.fecha_creacion >= today_start - timedelta(days=7),
        Pedido.estado != "CANCELADO",
    ).all()
    durations = []
    for order in delivered:
        c = order.fecha_creacion if order.fecha_creacion.tzinfo else order.fecha_creacion.replace(tzinfo=timezone.utc)
        d = order.fecha_entrega if order.fecha_entrega.tzinfo else order.fecha_entrega.replace(tzinfo=timezone.utc)
        mins = max(0.0, (d - c).total_seconds() / 60.0)
        durations.append(mins)
    avg_minutes = round(sum(durations) / len(durations), 1) if durations else 0.0
    active_orders = db.query(Pedido).filter(
        Pedido.estado.in_(["PENDIENTE", "COBRADO", "EN_PREPARACION", "LISTO"])
    ).all()
    overdue_count = 0
    for order in active_orders:
        if order.fecha_creacion:
            c = order.fecha_creacion if order.fecha_creacion.tzinfo else order.fecha_creacion.replace(tzinfo=timezone.utc)
            if (now - c).total_seconds() >= 15 * 60:
                overdue_count += 1
    return {
        "pedidos_medidos": len(durations),
        "tiempo_promedio_min": avg_minutes,
        "activos_en_cocina": len(active_orders),
        "atrasados_mas_15_min": overdue_count,
    }


@router.get("/reportes/rentabilidad")
def get_reporte_rentabilidad(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Producto.id,
            Producto.nombre,
            Producto.precio,
            Producto.costo_unitario,
            func.coalesce(func.sum(DetallePedido.cantidad), 0).label("unidades"),
            func.coalesce(func.sum(DetallePedido.subtotal), 0).label("ingresos"),
        )
        .join(DetallePedido, DetallePedido.producto_id == Producto.id)
        .join(Pedido, Pedido.id == DetallePedido.pedido_id)
        .filter(Pedido.estado_pago == "PAGADO", Pedido.estado != "CANCELADO")
        .group_by(Producto.id, Producto.nombre, Producto.precio, Producto.costo_unitario)
        .order_by(func.sum(DetallePedido.subtotal).desc())
        .all()
    )
    items = []
    total_ingresos = 0.0
    total_costos = 0.0
    for row in rows:
        recipe_rows = db.query(ProductoInsumo).filter(ProductoInsumo.producto_id == row.id).all()
        recipe_cost = sum(
            float(r.cantidad_por_unidad or 0) * float(r.insumo.costo_unitario or 0)
            for r in recipe_rows
            if r.insumo
        )
        unit_cost = recipe_cost if recipe_cost > 0 else float(row.costo_unitario or 0)
        unidades = int(row.unidades or 0)
        ingresos = round(float(row.ingresos or 0), 2)
        costo_total = round(unit_cost * unidades, 2)
        margen = round(ingresos - costo_total, 2)
        margen_pct = round((margen / ingresos * 100.0), 1) if ingresos > 0 else 0.0
        total_ingresos = round(total_ingresos + ingresos, 2)
        total_costos = round(total_costos + costo_total, 2)
        items.append({
            "producto_id": row.id,
            "nombre": row.nombre,
            "unidades_vendidas": unidades,
            "ingresos_usd": ingresos,
            "costo_unitario_usd": round(unit_cost, 2),
            "costo_total_usd": costo_total,
            "margen_usd": margen,
            "margen_pct": margen_pct,
        })
    return {
        "total_ingresos_usd": total_ingresos,
        "total_costos_usd": total_costos,
        "utilidad_bruta_usd": round(total_ingresos - total_costos, 2),
        "productos": items,
    }


@router.get("/reportes/exportar")
def exportar_reporte_ventas(
    formato: Literal["csv", "excel"] = "csv",
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Pedido)
        .filter(Pedido.estado_pago == "PAGADO", Pedido.estado != "CANCELADO")
        .order_by(Pedido.fecha_creacion.desc())
        .limit(1000)
        .all()
    )
    delimiter = ";" if formato == "excel" else ","
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=delimiter)
    writer.writerow([
        "Pedido_ID", "Fecha", "Factura", "Tipo", "Mesa", "Estado",
        "Subtotal_USD", "IVA_USD", "Descuento_USD", "Propina_USD", "Total_USD", "Metodo_Pago", "Moneda"
    ])
    for o in orders:
        writer.writerow([
            o.id,
            o.fecha_creacion.isoformat() if o.fecha_creacion else "",
            o.factura_numero or "",
            o.tipo or "",
            o.numero_mesa or "",
            o.estado or "",
            f"{float(o.subtotal or 0):.2f}",
            f"{float(o.impuesto or 0):.2f}",
            f"{float(o.descuento or 0):.2f}",
            f"{float(o.propina or 0):.2f}",
            f"{float(o.total or 0):.2f}",
            o.metodo_pago or "",
            o.moneda_pago or "USD",
        ])
    filename = "reporte_ventas_donde_david.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
