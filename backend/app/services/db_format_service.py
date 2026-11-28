"""Servicio seguro para formatear registros de la base de datos en orden referencial."""

from typing import Dict, Optional
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from backend.app.models.archivo_media import ArchivoMedia
from backend.app.models.arqueo_turno import ArqueoTurno
from backend.app.models.auditoria import Auditoria
from backend.app.models.categoria import Categoria
from backend.app.models.configuracion import Configuracion
from backend.app.models.detalle_pedido import DetallePedido
from backend.app.models.favorito_cliente import FavoritoCliente
from backend.app.models.guia_item import GuiaItem
from backend.app.models.insumo import Insumo
from backend.app.models.mesa import Mesa
from backend.app.models.movimiento_caja import MovimientoCaja
from backend.app.models.movimiento_inventario import MovimientoInventario
from backend.app.models.pedido import Pedido
from backend.app.models.producto import Producto
from backend.app.models.producto_insumo import ProductoInsumo
from backend.app.models.promocion import Promocion, promocion_productos
from backend.app.models.publicacion import Publicacion
from backend.app.models.puntos_log import PuntosLog
from backend.app.models.resena import Resena
from backend.app.models.solicitud_mesa import SolicitudMesa
from backend.app.models.turno import Turno
from backend.app.models.usuario import Usuario


ORDERED_DELETE_MODELS = [
    DetallePedido,
    SolicitudMesa,
    ArqueoTurno,
    MovimientoCaja,
    MovimientoInventario,
    PuntosLog,
    FavoritoCliente,
    ProductoInsumo,
    Resena,
    Auditoria,
    Pedido,
    Turno,
    Producto,
    Promocion,
    Insumo,
    Categoria,
    Mesa,
    Publicacion,
    GuiaItem,
    ArchivoMedia,
]


def format_database_records(
    db: Session,
    preserve_admin_id: Optional[int] = None,
    wipe_all_users_and_config: bool = False,
) -> Dict[str, int]:
    """
    Elimina registros operativos y de catálogo respetando claves foráneas en SQLite y PostgreSQL.
    Cuando preserve_admin_id es especificado, conserva esa cuenta administrativa y la bandera
    `is_installed` para evitar bloquear el acceso tras el formateo en producción.
    """
    deleted_counts: Dict[str, int] = {}
    bind = db.get_bind()
    existing_tables = set(inspect(bind).get_table_names())

    if promocion_productos.name in existing_tables:
        res = db.execute(promocion_productos.delete())
        deleted_counts[promocion_productos.name] = int(res.rowcount or 0)

    for model in ORDERED_DELETE_MODELS:
        table_name = model.__tablename__
        if table_name not in existing_tables:
            continue
        deleted_counts[table_name] = int(db.query(model).delete(synchronize_session=False) or 0)

    if "usuarios" in existing_tables:
        if wipe_all_users_and_config and preserve_admin_id is None:
            deleted_counts["usuarios"] = int(db.query(Usuario).delete(synchronize_session=False) or 0)
        elif preserve_admin_id is not None:
            deleted_counts["usuarios"] = int(
                db.query(Usuario).filter(Usuario.id != preserve_admin_id).delete(synchronize_session=False) or 0
            )
        else:
            deleted_counts["usuarios"] = int(
                db.query(Usuario).filter(Usuario.rol != "admin").delete(synchronize_session=False) or 0
            )

    if "configuraciones" in existing_tables:
        if wipe_all_users_and_config and preserve_admin_id is None:
            deleted_counts["configuraciones"] = int(db.query(Configuracion).delete(synchronize_session=False) or 0)
        else:
            deleted_counts["configuraciones"] = int(
                db.query(Configuracion)
                .filter(Configuracion.clave != "is_installed")
                .delete(synchronize_session=False)
                or 0
            )

    db.commit()

    # Reiniciar contadores autoincrementales cuando aplique
    dialect = bind.dialect.name if bind is not None else ""
    if dialect == "sqlite" and "sqlite_sequence" in existing_tables:
        try:
            db.execute(text("DELETE FROM sqlite_sequence"))
            db.commit()
        except Exception:
            db.rollback()
    elif dialect == "postgresql":
        for table_name in existing_tables:
            if table_name in {"alembic_version", "archivos_media", "promocion_productos"}:
                continue
            try:
                db.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('\"{table_name}\"', 'id'), "
                        f"COALESCE((SELECT MAX(id) FROM \"{table_name}\"), 0) + 1, false)"
                    )
                )
            except Exception:
                db.rollback()
        try:
            db.commit()
        except Exception:
            db.rollback()

    return deleted_counts
