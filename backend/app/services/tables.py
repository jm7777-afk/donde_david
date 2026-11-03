import re

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.app.models.mesa import Mesa
from backend.app.models.pedido import Pedido


def parse_table_number(table_name: str) -> int:
    match = re.fullmatch(r"\s*(?:mesa\s*)?(\d+)\s*", table_name, flags=re.IGNORECASE)
    if not match:
        raise ValueError(f"Número de mesa inválido: {table_name!r}")
    return int(match.group(1))


def refresh_table_state(db: Session, table_number: int) -> Mesa:
    db.flush()
    table = (
        db.query(Mesa)
        .filter(Mesa.numero_mesa == table_number)
        .with_for_update()
        .first()
    )
    if not table:
        raise ValueError(f"La Mesa #{table_number} no existe.")

    if has_active_table_orders(db, table_number):
        table.estado = "OCUPADA"
    else:
        table.estado = "PENDIENTE_LIMPIEZA"
    return table


def has_active_table_orders(db: Session, table_number: int) -> bool:
    active_order = db.query(Pedido.id).filter(
        Pedido.tipo == "mesa",
        Pedido.numero_mesa.in_([str(table_number), f"Mesa {table_number}"]),
        or_(
            Pedido.estado.notin_(["CANCELADO", "ENTREGADO"]),
            and_(Pedido.estado == "ENTREGADO", Pedido.estado_pago != "PAGADO"),
        ),
    ).first()
    return active_order is not None
