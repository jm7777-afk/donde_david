from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, LargeBinary, String
from backend.app.core.database import Base


class ArchivoMedia(Base):
    """Almacena archivos multimedia persistentes directamente en la base de datos."""

    __tablename__ = "archivos_media"

    id = Column(String(36), primary_key=True, index=True)
    nombre_archivo = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    tamano_bytes = Column(Integer, nullable=False)
    contenido = Column(LargeBinary, nullable=False)
    fecha_creacion = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
