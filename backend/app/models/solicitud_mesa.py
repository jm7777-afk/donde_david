from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from backend.app.core.database import Base


class SolicitudMesa(Base):
    __tablename__ = "solicitudes_mesa"

    id = Column(Integer, primary_key=True, index=True)
    mesa_id = Column(Integer, ForeignKey("mesas.id"), nullable=False, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    atendido_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    tipo = Column(String(30), nullable=False)
    estado = Column(String(20), nullable=False, default="PENDIENTE", index=True)
    nota = Column(Text, nullable=True)
    fecha_creacion = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    fecha_atencion = Column(DateTime, nullable=True)
