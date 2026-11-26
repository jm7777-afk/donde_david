"""Align auditoria constraints, index, and foreign key with ORM model."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9c1d2e3a4b5"
down_revision: Union[str, None] = "e1b2c3d4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE auditoria SET fecha = CURRENT_TIMESTAMP WHERE fecha IS NULL"))
    with op.batch_alter_table("auditoria") as batch_op:
        batch_op.alter_column(
            "detalle",
            existing_type=sa.String(length=255),
            type_=sa.String(length=500),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "fecha",
            existing_type=sa.DateTime(),
            nullable=False,
        )
        batch_op.create_index("ix_auditoria_usuario_id", ["usuario_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_auditoria_usuario_id_usuarios",
            "usuarios",
            ["usuario_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("auditoria") as batch_op:
        batch_op.drop_constraint("fk_auditoria_usuario_id_usuarios", type_="foreignkey")
        batch_op.drop_index("ix_auditoria_usuario_id")
        batch_op.alter_column(
            "fecha",
            existing_type=sa.DateTime(),
            nullable=True,
        )
        batch_op.alter_column(
            "detalle",
            existing_type=sa.String(length=500),
            type_=sa.String(length=255),
            existing_nullable=True,
        )
