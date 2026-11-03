"""Add courier live location and product loyalty snapshots."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d7e2a41f90"
down_revision: Union[str, None] = "9a3e6c1f4b72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "productos",
        sa.Column("puntos_fidelidad", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "detalles_pedido",
        sa.Column("puntos_fidelidad_unitarios", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("pedidos", sa.Column("puntos_otorgados", sa.Integer(), nullable=True))
    op.add_column("pedidos", sa.Column("repartidor_lat", sa.Numeric(10, 7), nullable=True))
    op.add_column("pedidos", sa.Column("repartidor_lng", sa.Numeric(10, 7), nullable=True))
    op.add_column("pedidos", sa.Column("ubicacion_repartidor_actualizada_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("pedidos", "ubicacion_repartidor_actualizada_at")
    op.drop_column("pedidos", "repartidor_lng")
    op.drop_column("pedidos", "repartidor_lat")
    op.drop_column("pedidos", "puntos_otorgados")
    op.drop_column("detalles_pedido", "puntos_fidelidad_unitarios")
    op.drop_column("productos", "puntos_fidelidad")
