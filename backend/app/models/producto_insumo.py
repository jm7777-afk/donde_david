from sqlalchemy import Column, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class ProductoInsumo(Base):
    """Vincula un producto del menú con los insumos base consumidos por unidad."""

    __tablename__ = "producto_insumos"
    __table_args__ = (
        UniqueConstraint("producto_id", "insumo_id", name="uq_producto_insumo_receta"),
    )

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id", ondelete="CASCADE"), nullable=False, index=True)
    insumo_id = Column(Integer, ForeignKey("insumos.id", ondelete="CASCADE"), nullable=False, index=True)
    cantidad_por_unidad = Column(Float, nullable=False, default=1.0)

    producto = relationship("Producto", backref="receta_insumos")
    insumo = relationship("Insumo", backref="productos_asociados")
