from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class FavoritoCliente(Base):
    """Productos marcados como favoritos por cada cliente autenticado."""

    __tablename__ = "favoritos_clientes"
    __table_args__ = (
        UniqueConstraint("usuario_id", "producto_id", name="uq_favorito_usuario_producto"),
    )

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id", ondelete="CASCADE"), nullable=False, index=True)
    fecha_creacion = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario")
    producto = relationship("Producto")
