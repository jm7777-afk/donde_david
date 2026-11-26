"""Add promocion_productos association table."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c2d3e4f5b6"
down_revision: Union[str, None] = "f9c1d2e3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "promocion_productos",
        sa.Column("promocion_id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["promocion_id"], ["promociones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("promocion_id", "producto_id"),
    )


def downgrade() -> None:
    op.drop_table("promocion_productos")
