from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, UniqueConstraint

from backend.app.core.database import Base


class ArqueoTurno(Base):
    __tablename__ = "arqueos_turno"
    __table_args__ = (
        UniqueConstraint("turno_id", "metodo_pago", name="uq_arqueos_turno_metodo"),
    )

    id = Column(Integer, primary_key=True, index=True)
    turno_id = Column(Integer, ForeignKey("turnos.id"), nullable=False, index=True)
    metodo_pago = Column(String(50), nullable=False)
    esperado_usd = Column(Numeric(12, 2), nullable=False)
    contado_usd = Column(Numeric(12, 2), nullable=False)
    diferencia_usd = Column(Numeric(12, 2), nullable=False)
