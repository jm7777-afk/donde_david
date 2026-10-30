"""Add payment verification and courier delivery fields.

Revision ID: a8f41c9d27b6
Revises: 3ce5b3ccc3f0
Create Date: 2026-10-24 12:25:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8f41c9d27b6"
down_revision: Union[str, None] = "3ce5b3ccc3f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pedidos", sa.Column("estado_pago", sa.String(length=30), nullable=False, server_default="PENDIENTE"))
    op.add_column("pedidos", sa.Column("moneda_pago", sa.String(length=3), nullable=False, server_default="USD"))
    op.add_column("pedidos", sa.Column("monto_pago", sa.Numeric(12, 2), nullable=True))
    op.add_column("pedidos", sa.Column("tasa_cambio_pago", sa.Numeric(12, 4), nullable=True))
    op.add_column("pedidos", sa.Column("referencia_pago", sa.String(length=100), nullable=True))
    op.add_column("pedidos", sa.Column("repartidor_id", sa.Integer(), nullable=True))
    op.add_column("pedidos", sa.Column("estado_delivery", sa.String(length=30), nullable=True))
    op.add_column("pedidos", sa.Column("fecha_retiro", sa.DateTime(), nullable=True))
    op.add_column("pedidos", sa.Column("fecha_en_camino", sa.DateTime(), nullable=True))
    with op.batch_alter_table("pedidos") as batch_op:
        batch_op.create_foreign_key(
            "fk_pedidos_repartidor_id_usuarios",
            "usuarios",
            ["repartidor_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("pedidos") as batch_op:
        batch_op.drop_constraint("fk_pedidos_repartidor_id_usuarios", type_="foreignkey")
        batch_op.drop_column("fecha_en_camino")
        batch_op.drop_column("fecha_retiro")
        batch_op.drop_column("estado_delivery")
        batch_op.drop_column("repartidor_id")
        batch_op.drop_column("referencia_pago")
        batch_op.drop_column("tasa_cambio_pago")
        batch_op.drop_column("monto_pago")
        batch_op.drop_column("moneda_pago")
        batch_op.drop_column("estado_pago")
