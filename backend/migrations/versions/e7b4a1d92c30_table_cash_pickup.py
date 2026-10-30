"""Add table requests, cash reconciliation, and pickup verification."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b4a1d92c30"
down_revision: Union[str, None] = "d514e8a2c9f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("pedidos", sa.Column("codigo_retiro", sa.String(length=6), nullable=True))
    op.add_column("pedidos", sa.Column("estado_retiro", sa.String(length=30), nullable=True))

    op.create_table(
        "solicitudes_mesa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mesa_id", sa.Integer(), nullable=False),
        sa.Column("pedido_id", sa.Integer(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("atendido_por_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("nota", sa.Text(), nullable=True),
        sa.Column("fecha_creacion", sa.DateTime(), nullable=False),
        sa.Column("fecha_atencion", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["mesa_id"], ["mesas.id"]),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.ForeignKeyConstraint(["atendido_por_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_solicitudes_mesa_mesa_id", "solicitudes_mesa", ["mesa_id"])
    op.create_index("ix_solicitudes_mesa_pedido_id", "solicitudes_mesa", ["pedido_id"])
    op.create_index("ix_solicitudes_mesa_estado", "solicitudes_mesa", ["estado"])
    op.create_index("ix_solicitudes_mesa_id", "solicitudes_mesa", ["id"])

    op.create_table(
        "movimientos_caja",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turno_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("metodo_pago", sa.String(length=50), nullable=False),
        sa.Column("monto_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("concepto", sa.String(length=150), nullable=False),
        sa.Column("observacion", sa.Text(), nullable=True),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["turno_id"], ["turnos.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_movimientos_caja_turno_id", "movimientos_caja", ["turno_id"])
    op.create_index("ix_movimientos_caja_id", "movimientos_caja", ["id"])

    op.create_table(
        "arqueos_turno",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turno_id", sa.Integer(), nullable=False),
        sa.Column("metodo_pago", sa.String(length=50), nullable=False),
        sa.Column("esperado_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("contado_usd", sa.Numeric(12, 2), nullable=False),
        sa.Column("diferencia_usd", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["turno_id"], ["turnos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("turno_id", "metodo_pago", name="uq_arqueos_turno_metodo"),
    )
    op.create_index("ix_arqueos_turno_turno_id", "arqueos_turno", ["turno_id"])
    op.create_index("ix_arqueos_turno_id", "arqueos_turno", ["id"])


def downgrade() -> None:
    op.drop_index("ix_arqueos_turno_id", table_name="arqueos_turno")
    op.drop_index("ix_arqueos_turno_turno_id", table_name="arqueos_turno")
    op.drop_table("arqueos_turno")
    op.drop_index("ix_movimientos_caja_id", table_name="movimientos_caja")
    op.drop_index("ix_movimientos_caja_turno_id", table_name="movimientos_caja")
    op.drop_table("movimientos_caja")
    op.drop_index("ix_solicitudes_mesa_id", table_name="solicitudes_mesa")
    op.drop_index("ix_solicitudes_mesa_estado", table_name="solicitudes_mesa")
    op.drop_index("ix_solicitudes_pedido_id", table_name="solicitudes_mesa")
    op.drop_index("ix_solicitudes_mesa_mesa_id", table_name="solicitudes_mesa")
    op.drop_table("solicitudes_mesa")
    op.drop_column("pedidos", "estado_retiro")
    op.drop_column("pedidos", "codigo_retiro")
