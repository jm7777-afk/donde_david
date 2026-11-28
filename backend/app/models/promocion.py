from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, Numeric, String, Table
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


promocion_productos = Table(
    "promocion_productos",
    Base.metadata,
    Column("promocion_id", Integer, ForeignKey("promociones.id", ondelete="CASCADE"), primary_key=True),
    Column("producto_id", Integer, ForeignKey("productos.id", ondelete="CASCADE"), primary_key=True),
)


class Promocion(Base):
    __tablename__ = "promociones"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String(150), nullable=False)
    descripcion = Column(String(255), nullable=True)
    descuento_pct = Column(Float, default=0.0) # e.g. 20% off
    precio_global = Column(Numeric(12, 2), nullable=True)
    codigo_cupon = Column(String(50), nullable=True, unique=True)
    banner_url = Column(String(500), nullable=True)
    activo = Column(Boolean, default=True)
    fecha_inicio = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    fecha_fin = Column(DateTime, nullable=True)
    dias_semana = Column(String(40), nullable=True)
    hora_inicio = Column(String(5), nullable=True)
    hora_fin = Column(String(5), nullable=True)

    productos = relationship("Producto", secondary=promocion_productos, lazy="selectin")
