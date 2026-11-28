"""Add precio_global to promociones."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2d4e5f6a7c8"
down_revision: Union[str, None] = "a1c2d3e4f5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("promociones") as batch_op:
        batch_op.add_column(sa.Column("precio_global", sa.Numeric(precision=12, scale=2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("promociones") as batch_op:
        batch_op.drop_column("precio_global")

