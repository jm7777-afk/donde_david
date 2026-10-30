from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text

from backend.app.core.database import Base


class MovimientoCaja(Base):
    __tablename__ = "movimientos_caja"

    id = Column(Integer, primary_key=True, index=True)
    turno_id = Column(Integer, ForeignKey("turnos.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    tipo = Column(String(20), nullable=False, default="EGRESO")
    metodo_pago = Column(String(50), nullable=False, default="Efectivo")
    monto_usd = Column(Numeric(12, 2), nullable=False)
    concepto = Column(String(150), nullable=False)
    observacion = Column(Text, nullable=True)
    fecha = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
