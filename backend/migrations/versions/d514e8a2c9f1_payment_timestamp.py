"""Track the time a payment is confirmed."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d514e8a2c9f1"
down_revision: Union[str, None] = "c13d8a1f6b02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pedidos", sa.Column("fecha_pago", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("pedidos", "fecha_pago")
