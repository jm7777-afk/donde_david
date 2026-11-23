from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime, timezone
from backend.app.core.database import Base
from backend.app.models.auditoria import Auditoria

class PuntosLog(Base):
    __tablename__ = "puntos_log"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    puntos = Column(Integer, nullable=False) # e.g. +100 or -30
    concepto = Column(String(200), nullable=False) # e.g. "Pedido #1087", "Canje de recompensa"
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=True)
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc))

__all__ = ["PuntosLog", "Auditoria"]
