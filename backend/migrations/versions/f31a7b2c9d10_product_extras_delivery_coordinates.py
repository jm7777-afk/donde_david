"""Add configurable product extras/media and structured delivery coordinates."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f31a7b2c9d10"
down_revision: Union[str, None] = "e7b4a1d92c30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("productos", sa.Column("extras_json", sa.Text(), nullable=True))
    op.add_column("productos", sa.Column("media_json", sa.Text(), nullable=True))
    op.add_column("pedidos", sa.Column("delivery_lat", sa.Numeric(10, 7), nullable=True))
    op.add_column("pedidos", sa.Column("delivery_lng", sa.Numeric(10, 7), nullable=True))


def downgrade() -> None:
    op.drop_column("pedidos", "delivery_lng")
    op.drop_column("pedidos", "delivery_lat")
    op.drop_column("productos", "media_json")
    op.drop_column("productos", "extras_json")
