"""Add product availability and declared allergen metadata.

Revision ID: c13d8a1f6b02
Revises: a8f41c9d27b6
Create Date: 2026-10-24 13:45:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c13d8a1f6b02"
down_revision: Union[str, None] = "a8f41c9d27b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("productos", sa.Column("alergenos", sa.String(length=500), nullable=True))
    op.add_column(
        "productos",
        sa.Column("disponible", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("productos", "disponible")
    op.drop_column("productos", "alergenos")
