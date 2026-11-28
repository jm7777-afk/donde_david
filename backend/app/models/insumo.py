from sqlalchemy import Column, Integer, String, Float, DateTime, Numeric
from datetime import datetime, timezone
from backend.app.core.database import Base

class Insumo(Base):
    __tablename__ = "insumos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, unique=True)
    stock_actual = Column(Float, nullable=False, default=0.0)
    stock_minimo = Column(Float, nullable=False, default=5.0)
    unidad_medida = Column(String(20), default="kg") # kg, un, lt
    costo_unitario = Column(Numeric(12, 2), nullable=False, default=0.00, server_default="0")
    estado = Column(String(30), default="NORMAL") # NORMAL, CRITICO
    fecha_actualizacion = Column(DateTime, default=lambda: datetime.now(timezone.utc))
