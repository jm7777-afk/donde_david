"""Add enhanced audit trail columns for enterprise traceability."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "e1b2c3d4f5a6"
down_revision: Union[str, None] = "c8d7e2a41f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("auditoria") as batch_op:
        batch_op.add_column(sa.Column("usuario_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("ip_address", sa.String(length=45), nullable=True))
        batch_op.add_column(sa.Column("recurso", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("recurso_id", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("datos_previos", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("datos_nuevos", sa.Text(), nullable=True))
        batch_op.create_index("ix_auditoria_accion", ["accion"])
        batch_op.create_index("ix_auditoria_usuario", ["usuario"])
        batch_op.create_index("ix_auditoria_recurso", ["recurso"])
        batch_op.create_index("ix_auditoria_fecha", ["fecha"])


def downgrade() -> None:
    with op.batch_alter_table("auditoria") as batch_op:
        batch_op.drop_index("ix_auditoria_fecha")
        batch_op.drop_index("ix_auditoria_recurso")
        batch_op.drop_index("ix_auditoria_usuario")
        batch_op.drop_index("ix_auditoria_accion")
        batch_op.drop_column("datos_nuevos")
        batch_op.drop_column("datos_previos")
        batch_op.drop_column("recurso_id")
        batch_op.drop_column("recurso")
        batch_op.drop_column("ip_address")
        batch_op.drop_column("usuario_id")
