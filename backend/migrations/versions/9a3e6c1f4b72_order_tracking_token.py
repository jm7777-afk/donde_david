"""Add opaque customer order tracking tokens."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9a3e6c1f4b72"
down_revision: Union[str, None] = "f31a7b2c9d10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pedidos", sa.Column("token_seguimiento_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("pedidos", "token_seguimiento_hash")
