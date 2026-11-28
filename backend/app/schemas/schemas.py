from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional, List, Literal
from datetime import datetime


# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    usuario: dict


class LoginRequest(BaseModel):
    nombre_usuario: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=72)


# User Schemas
class UsuarioBase(BaseModel):
    nombre: str
    apellido: str
    email: str
    telefono: Optional[str] = None
    nombre_usuario: str
    rol: str
    activo: Optional[bool] = True


class UsuarioCreate(UsuarioBase):
    password: str = Field(min_length=12, max_length=72)


class UsuarioOut(UsuarioBase):
    id: int
    fecha_creacion: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ==================== SCHEMAS: AUDITORIA ====================
class AuditoriaOut(BaseModel):
    id: int
    accion: str
    usuario: str
    usuario_id: Optional[int] = None
    ip_address: Optional[str] = None
    recurso: Optional[str] = None
    recurso_id: Optional[str] = None
    detalle: Optional[str] = None
    datos_previos: Optional[str] = None
    datos_nuevos: Optional[str] = None
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditoriaListOut(BaseModel):
    total: int
    items: List[AuditoriaOut]
    acciones_disponibles: List[str] = Field(default_factory=list)
    recursos_disponibles: List[str] = Field(default_factory=list)


# ==================== SCHEMAS: LOGS ====================
class LogEntryOut(BaseModel):
    timestamp: Optional[str] = None
    level: str
    logger: str
    message: str
    raw: str


class LogResponseOut(BaseModel):
    file: str
    size_kb: float
    total_returned: int
    logs: List[LogEntryOut]


class LogStatsOut(BaseModel):
    total_recent_events: int
    counts_by_level: dict[str, int]
    error_rate_percentage: float
    app_log_size_kb: float
    error_log_size_kb: float


# ==================== SCHEMAS: BACKUPS ====================
class BackupCreateRequest(BaseModel):
    descripcion: Optional[str] = Field(default=None, max_length=255)


class BackupOut(BaseModel):
    filename: str
    engine: str
    created_at: str
    created_by: str
    description: Optional[str] = None
    size_bytes: int
    size_human: str
    sha256: str
    status: str


class BackupRestoreResponse(BaseModel):
    mensaje: str
    checkpoint_previo: Optional[str] = None
    tablas_restauradas: Optional[List[str]] = None
    restaurado_por: str
    timestamp: str


# Categoria Schemas
class CategoriaBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    imagen_url: Optional[str] = None
    orden: Optional[int] = 0
    activo: Optional[bool] = True


class CategoriaCreate(CategoriaBase):
    pass


class CategoriaOut(CategoriaBase):
    id: int
    fecha_creacion: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Producto Schemas
class ProductoBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    precio: float = Field(ge=0, allow_inf_nan=False)
    precio_promocion: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    costo_unitario: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    stock: Optional[int] = Field(default=50, ge=0)
    stock_minimo: Optional[int] = Field(default=5, ge=0)
    puntos_fidelidad: int = Field(default=0, ge=0, le=100000)
    imagen_url: Optional[str] = None
    tiempo_preparacion: Optional[int] = 15
    personalizable: Optional[bool] = True
    ingredientes_json: Optional[str] = None
    extras_json: Optional[str] = None
    media_json: Optional[str] = None
    alergenos: Optional[str] = Field(default=None, max_length=500)
    disponible: Optional[bool] = True
    activo: Optional[bool] = True
    categoria_id: int


class ProductoCreate(ProductoBase):
    pass


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    precio_promocion: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    costo_unitario: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    stock: Optional[int] = Field(default=None, ge=0)
    puntos_fidelidad: Optional[int] = Field(default=None, ge=0, le=100000)
    imagen_url: Optional[str] = None
    categoria_id: Optional[int] = None
    ingredientes_json: Optional[str] = None
    extras_json: Optional[str] = None
    media_json: Optional[str] = None
    alergenos: Optional[str] = Field(default=None, max_length=500)
    disponible: Optional[bool] = None
    activo: Optional[bool] = None


class ProductoOut(ProductoBase):
    id: int
    categoria: Optional[CategoriaOut] = None

    model_config = ConfigDict(from_attributes=True)


# Promocion Schemas
class PromocionCreate(BaseModel):
    titulo: str
    descripcion: Optional[str] = None
    descuento_pct: Optional[float] = 0.0
    precio_global: Optional[float] = None
    codigo_cupon: Optional[str] = None
    banner_url: Optional[str] = None
    activo: Optional[bool] = True
    dias_semana: Optional[str] = None
    hora_inicio: Optional[str] = None
    hora_fin: Optional[str] = None


class PromocionOut(PromocionCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


# Resena Schemas
class ResenaCreate(BaseModel):
    nombre_cliente: str = Field(min_length=1, max_length=150)
    comentario: str = Field(min_length=1, max_length=2000)
    estrellas: Optional[int] = Field(default=5, ge=1, le=5)
    foto_url: Optional[str] = None


class ResenaPedidoCreate(BaseModel):
    estrellas: int = Field(ge=1, le=5)
    comentario: str = Field(min_length=2, max_length=2000)
    nombre_cliente: Optional[str] = Field(default=None, max_length=150)


class ResenaOut(ResenaCreate):
    id: int
    pedido_id: Optional[int] = None
    fecha_creacion: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Publicacion Schemas
class PublicacionCreate(BaseModel):
    titulo: str
    contenido: str
    imagen_url: Optional[str] = None
    autor: Optional[str] = "Donde David"
    activo: Optional[bool] = True


class PublicacionOut(PublicacionCreate):
    id: int
    fecha_creacion: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Cambiar Mesa Request
class CambiarMesaRequest(BaseModel):
    nueva_mesa: int = Field(gt=0)


# OTP Verify Request
class OTPVerifyRequest(BaseModel):
    pedido_id: int
    codigo_otp: str


# Detalle Pedido Schemas
class DetallePedidoItem(BaseModel):
    producto_id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=100)
    personalizaciones: Optional[dict] = None
    observaciones: Optional[str] = None


class PromocionPedidoItem(BaseModel):
    promocion_id: int = Field(gt=0)
    cantidad: int = Field(default=1, gt=0, le=50)


class DetallePedidoOut(BaseModel):
    id: int
    producto_id: int
    cantidad: int
    precio_unitario: float
    subtotal: float
    puntos_fidelidad_unitarios: int = 0
    personalizaciones: Optional[str] = None
    estado: str
    observaciones: Optional[str] = None
    producto: Optional[ProductoOut] = None

    model_config = ConfigDict(from_attributes=True)


# Pedido Schemas
class PedidoCreate(BaseModel):
    numero_mesa: str = Field(min_length=1, max_length=50)
    codigo_qr: Optional[str] = None
    tipo: Optional[Literal["mesa", "llevar", "delivery"]] = "mesa"
    modo_pago: Optional[str] = "PAGAR_ANTES"  # PAGAR_ANTES, PAGAR_DESPUES
    observaciones: Optional[str] = None
    nombre_cliente_delivery: Optional[str] = None
    telefono_delivery: Optional[str] = None
    direccion_delivery: Optional[str] = None
    delivery_lat: Optional[float] = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    delivery_lng: Optional[float] = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    metodo_pago: Optional[str] = Field(default=None, max_length=50)
    moneda_pago: Optional[str] = Field(default="USD", pattern="^(USD|VES)$")
    referencia_pago: Optional[str] = Field(default=None, max_length=100)
    codigo_cupon: Optional[str] = Field(default=None, max_length=50)
    propina: float = Field(default=0.0, ge=0, le=500, allow_inf_nan=False)
    detalles: List[DetallePedidoItem] = Field(min_length=1, max_length=50)
    promociones: List[PromocionPedidoItem] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_delivery_coordinates(self):
        if (self.delivery_lat is None) != (self.delivery_lng is None):
            raise ValueError("La latitud y longitud deben enviarse juntas.")
        if self.tipo != "delivery" and self.delivery_lat is not None:
            raise ValueError("Las coordenadas solo aplican a pedidos delivery.")
        return self


class SolicitudMesaCreate(BaseModel):
    numero_mesa: int = Field(gt=0)
    tipo: Literal["LLAMAR_MESERO", "SOLICITAR_CUENTA"]
    pedido_id: Optional[int] = Field(default=None, gt=0)
    nota: Optional[str] = Field(default=None, max_length=250)


class SolicitudMesaEstado(BaseModel):
    estado: Literal["ATENDIDA", "CANCELADA"]


class MesaLimpiezaRequest(BaseModel):
    accion: Literal["INICIAR", "FINALIZAR"]


class MovimientoCajaCreate(BaseModel):
    concepto: str = Field(min_length=3, max_length=150)
    monto_usd: float = Field(gt=0, allow_inf_nan=False)
    metodo_pago: Literal["Efectivo", "Pago Móvil", "Punto de Venta"] = "Efectivo"
    observacion: Optional[str] = Field(default=None, max_length=300)


class MovimientoCajaOut(BaseModel):
    id: int
    turno_id: int
    usuario_id: int
    tipo: str
    metodo_pago: str
    monto_usd: float
    concepto: str
    observacion: Optional[str] = None
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class ArqueoTurnoInput(BaseModel):
    metodo_pago: Literal["Efectivo", "Pago Móvil", "Punto de Venta"]
    contado_usd: float = Field(ge=0, allow_inf_nan=False)


class ArqueoTurnoOut(BaseModel):
    metodo_pago: str
    esperado_usd: float
    contado_usd: float
    diferencia_usd: float

    model_config = ConfigDict(from_attributes=True)


class PedidoBaseOut(BaseModel):
    id: int
    numero_mesa: str
    codigo_qr: Optional[str] = None
    tipo: str
    modo_pago: Optional[str] = "PAGAR_ANTES"
    estado: str
    subtotal: float
    impuesto: float
    costo_empaque: Optional[float] = 0.0
    descuento: float
    propina: float = 0.0
    total: float
    observaciones: Optional[str] = None
    nombre_cliente_delivery: Optional[str] = None
    telefono_delivery: Optional[str] = None
    direccion_delivery: Optional[str] = None
    delivery_lat: Optional[float] = None
    delivery_lng: Optional[float] = None
    otp_verificado: Optional[bool] = False
    estado_retiro: Optional[str] = None
    fecha_creacion: Optional[datetime] = None
    fecha_pago: Optional[datetime] = None
    metodo_pago: Optional[str] = None
    estado_pago: str = "PENDIENTE"
    moneda_pago: str = "USD"
    monto_pago: Optional[float] = None
    tasa_cambio_pago: Optional[float] = None
    referencia_pago: Optional[str] = None
    pagos_mixtos_json: Optional[str] = None
    repartidor_id: Optional[int] = None
    estado_delivery: Optional[str] = None
    fecha_retiro: Optional[datetime] = None
    fecha_en_camino: Optional[datetime] = None
    monto_recibido: Optional[float] = None
    cambio: Optional[float] = None
    factura_numero: Optional[str] = None
    nit_cliente: Optional[str] = None
    nombre_factura: Optional[str] = None
    detalles: List[DetallePedidoOut] = []

    model_config = ConfigDict(from_attributes=True)


class PedidoOut(PedidoBaseOut):
    codigo_otp: Optional[str] = None


class PedidoCreadoOut(PedidoOut):
    codigo_retiro: Optional[str] = None
    token_seguimiento: Optional[str] = None


class ConfirmarRetiroRequest(BaseModel):
    codigo_retiro: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")


class PagoMixtoItem(BaseModel):
    metodo_pago: Literal["Efectivo", "Pago Móvil", "Punto de Venta"]
    monto_usd: float = Field(gt=0, allow_inf_nan=False)
    moneda: Literal["USD", "VES"] = "USD"
    referencia: Optional[str] = Field(default=None, max_length=100)


# Payment Request Schema
class CobrarPedidoRequest(BaseModel):
    metodo_pago: str = Field(min_length=1, max_length=50)
    monto_recibido: float = Field(ge=0, allow_inf_nan=False)
    moneda_pago: str = Field(default="USD", pattern="^(USD|VES)$")
    nit_cliente: Optional[str] = "CF"
    nombre_factura: Optional[str] = "Consumidor Final"
    propina: Optional[float] = Field(default=None, ge=0, le=500, allow_inf_nan=False)
    pagos_mixtos: Optional[List[PagoMixtoItem]] = Field(default=None, max_length=4)


class DividirCuentaRequest(BaseModel):
    modo: Literal["igual", "items"]
    partes: Optional[int] = Field(default=None, ge=2, le=10)
    detalle_ids: Optional[List[int]] = Field(default=None)


class CuponValidarRequest(BaseModel):
    codigo_cupon: str = Field(min_length=1, max_length=50)
    producto_ids: List[int] = Field(default_factory=list)


class RecetaInsumoItem(BaseModel):
    insumo_id: int = Field(gt=0)
    cantidad_por_unidad: float = Field(gt=0, le=1000, allow_inf_nan=False)


class RecetaUpdateRequest(BaseModel):
    items: List[RecetaInsumoItem] = Field(default_factory=list, max_length=40)


class ConfirmarPagoRequest(BaseModel):
    aprobado: bool
    observacion: Optional[str] = Field(default=None, max_length=250)


class AsignarRepartidorRequest(BaseModel):
    repartidor_id: int = Field(gt=0)


class EstadoDeliveryRequest(BaseModel):
    estado: str = Field(pattern="^(RECOGIDO|EN_CAMINO)$")


class UbicacionRepartidorRequest(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)


class EntregaDeliveryRequest(BaseModel):
    codigo_otp: str = Field(min_length=6, max_length=6, pattern="^[0-9]{6}$")


# Turno Schemas
class TurnoApertura(BaseModel):
    monto_apertura: float = Field(ge=0, allow_inf_nan=False)


class TurnoCierre(BaseModel):
    monto_cierre: float = Field(ge=0, allow_inf_nan=False)
    arqueo: Optional[List[ArqueoTurnoInput]] = Field(default=None, max_length=3)


class TurnoOut(BaseModel):
    id: int
    numero_turno: int
    fecha_apertura: datetime
    fecha_cierre: Optional[datetime] = None
    monto_apertura: float
    monto_cierre: Optional[float] = None
    total_ventas: float
    total_pedidos: int
    efectivo_declarado: Optional[float] = None
    efectivo_esperado: Optional[float] = None
    diferencia: Optional[float] = None
    activo: bool
    usuario_caja_id: int
    arqueo: List[ArqueoTurnoOut] = Field(default_factory=list)
    esperado_por_metodo: dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)
