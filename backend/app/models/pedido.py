from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.app.core.database import Base

class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)
    numero_mesa = Column(String(50), nullable=False) # e.g. "Mesa 5" or "Delivery #105"
    codigo_qr = Column(String(100), nullable=True)
    tipo = Column(String(30), default="mesa") # mesa, llevar, delivery
    modo_pago = Column(String(30), default="PAGAR_ANTES") # PAGAR_ANTES, PAGAR_DESPUES (Cuenta Abierta)
    estado = Column(String(30), default="PENDIENTE") # PENDIENTE, EN_PREPARACION, LISTO, COBRADO, ENTREGADO, CANCELADO
    subtotal = Column(Numeric(12, 2), nullable=False, default=0.00)
    impuesto = Column(Numeric(12, 2), nullable=False, default=0.00) # 16% IVA
    costo_empaque = Column(Numeric(12, 2), default=0.00)
    descuento = Column(Numeric(12, 2), default=0.00)
    total = Column(Numeric(12, 2), nullable=False, default=0.00)
    observaciones = Column(Text, nullable=True)
    
    # Campos exclusivos para Delivery & OTP
    nombre_cliente_delivery = Column(String(150), nullable=True)
    telefono_delivery = Column(String(50), nullable=True)
    direccion_delivery = Column(Text, nullable=True)
    delivery_lat = Column(Numeric(10, 7), nullable=True)
    delivery_lng = Column(Numeric(10, 7), nullable=True)
    codigo_otp = Column(String(10), nullable=True)
    otp_verificado = Column(Boolean, default=False)
    codigo_retiro = Column(String(6), nullable=True)
    estado_retiro = Column(String(30), nullable=True)
    
    fecha_creacion = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    fecha_pago = Column(DateTime, nullable=True)
    fecha_entrega = Column(DateTime, nullable=True)
    metodo_pago = Column(String(50), nullable=True) # Efectivo, Tarjeta, QR, Puntos
    monto_recibido = Column(Numeric(12, 2), nullable=True)
    cambio = Column(Numeric(12, 2), nullable=True)
    estado_pago = Column(String(30), nullable=False, default="PENDIENTE")
    moneda_pago = Column(String(3), nullable=False, default="USD")
    monto_pago = Column(Numeric(12, 2), nullable=True)
    tasa_cambio_pago = Column(Numeric(12, 4), nullable=True)
    referencia_pago = Column(String(100), nullable=True)
    repartidor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    estado_delivery = Column(String(30), nullable=True)
    fecha_retiro = Column(DateTime, nullable=True)
    fecha_en_camino = Column(DateTime, nullable=True)
    factura_numero = Column(String(50), nullable=True)
    nit_cliente = Column(String(50), default="CF")
    nombre_factura = Column(String(100), default="Consumidor Final")
    
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    turno_id = Column(Integer, ForeignKey("turnos.id"), nullable=True)

    detalles = relationship("DetallePedido", back_populates="pedido", cascade="all, delete-orphan")
    usuario = relationship("Usuario", foreign_keys=[usuario_id])
    repartidor = relationship("Usuario", foreign_keys=[repartidor_id])
    turno = relationship("Turno")
