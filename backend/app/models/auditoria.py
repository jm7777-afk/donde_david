"""
Modelo de Auditoría (Audit Trail) para trazabilidad integral de acciones en Donde David.
Registra eventos críticos del sistema, usuarios, mutaciones de datos, seguridad y operaciones financieras.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from backend.app.core.database import Base


class Auditoria(Base):
    """
    Entidad de persistencia para el registro de auditoría del sistema.
    Permite trazabilidad completa de qué usuario realizó qué acción,
    sobre qué recurso, desde qué IP y en qué fecha/hora exacta.
    """
    __tablename__ = "auditoria"

    id = Column(Integer, primary_key=True, index=True)
    accion = Column(String(100), nullable=False, index=True)          # Ej: LOGIN_SUCCESS, STOCK_ADJUST, SHIFT_OPEN
    usuario = Column(String(100), nullable=False, index=True)        # Nombre de usuario o 'sistema'
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)                   # Dirección IP IPv4 o IPv6
    recurso = Column(String(100), nullable=True, index=True)         # Tabla/Entidad afectada: productos, pedidos, etc.
    recurso_id = Column(String(50), nullable=True)                  # Identificador del registro afectado
    detalle = Column(String(500), nullable=True)                     # Descripción legible para humanos
    datos_previos = Column(Text, nullable=True)                      # JSON serializado con estado antes del cambio
    datos_nuevos = Column(Text, nullable=True)                       # JSON serializado con estado posterior al cambio
    fecha = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<Auditoria(id={self.id}, accion='{self.accion}', usuario='{self.usuario}', fecha={self.fecha})>"
