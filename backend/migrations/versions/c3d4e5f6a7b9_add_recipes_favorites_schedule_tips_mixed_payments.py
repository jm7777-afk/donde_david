"""Add recipes, customer favorites, promo schedules, table zones, tips, mixed payments, and inventory costs.

Revision ID: c3d4e5f6a7b9
Revises: b2d4e5f6a7c8
Create Date: 2026-11-27 22:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b9"
down_revision = "b2d4e5f6a7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("promociones", sa.Column("dias_semana", sa.String(length=40), nullable=True))
    op.add_column("promociones", sa.Column("hora_inicio", sa.String(length=5), nullable=True))
    op.add_column("promociones", sa.Column("hora_fin", sa.String(length=5), nullable=True))

    op.add_column("mesas", sa.Column("zona", sa.String(length=40), nullable=False, server_default="Salón"))

    op.add_column("pedidos", sa.Column("propina", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"))
    op.add_column("pedidos", sa.Column("pagos_mixtos_json", sa.Text(), nullable=True))

    op.add_column("productos", sa.Column("costo_unitario", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"))
    op.add_column("insumos", sa.Column("costo_unitario", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"))

    op.add_column("movimientos_inventario", sa.Column("costo_unitario", sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column("movimientos_inventario", sa.Column("proveedor", sa.String(length=150), nullable=True))

    with op.batch_alter_table("resenas") as batch_op:
        batch_op.add_column(sa.Column("pedido_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("usuario_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_resenas_pedido_id", ["pedido_id"], unique=False)
        batch_op.create_foreign_key("fk_resenas_pedido_id", "pedidos", ["pedido_id"], ["id"])
        batch_op.create_foreign_key("fk_resenas_usuario_id", "usuarios", ["usuario_id"], ["id"])

    op.create_table(
        "producto_insumos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("insumo_id", sa.Integer(), nullable=False),
        sa.Column("cantidad_por_unidad", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["insumo_id"], ["insumos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("producto_id", "insumo_id", name="uq_producto_insumo_receta"),
    )
    op.create_index("ix_producto_insumos_id", "producto_insumos", ["id"], unique=False)
    op.create_index("ix_producto_insumos_insumo_id", "producto_insumos", ["insumo_id"], unique=False)
    op.create_index("ix_producto_insumos_producto_id", "producto_insumos", ["producto_id"], unique=False)

    op.create_table(
        "favoritos_clientes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id", "producto_id", name="uq_favorito_usuario_producto"),
    )
    op.create_index("ix_favoritos_clientes_id", "favoritos_clientes", ["id"], unique=False)
    op.create_index("ix_favoritos_clientes_producto_id", "favoritos_clientes", ["producto_id"], unique=False)
    op.create_index("ix_favoritos_clientes_usuario_id", "favoritos_clientes", ["usuario_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_favoritos_clientes_usuario_id", table_name="favoritos_clientes")
    op.drop_index("ix_favoritos_clientes_producto_id", table_name="favoritos_clientes")
    op.drop_index("ix_favoritos_clientes_id", table_name="favoritos_clientes")
    op.drop_table("favoritos_clientes")

    op.drop_index("ix_producto_insumos_producto_id", table_name="producto_insumos")
    op.drop_index("ix_producto_insumos_insumo_id", table_name="producto_insumos")
    op.drop_index("ix_producto_insumos_id", table_name="producto_insumos")
    op.drop_table("producto_insumos")

    with op.batch_alter_table("resenas") as batch_op:
        batch_op.drop_constraint("fk_resenas_usuario_id", type_="foreignkey")
        batch_op.drop_constraint("fk_resenas_pedido_id", type_="foreignkey")
        batch_op.drop_index("ix_resenas_pedido_id")
        batch_op.drop_column("usuario_id")
        batch_op.drop_column("pedido_id")

    op.drop_column("movimientos_inventario", "proveedor")
    op.drop_column("movimientos_inventario", "costo_unitario")
    op.drop_column("insumos", "costo_unitario")
    op.drop_column("productos", "costo_unitario")
    op.drop_column("pedidos", "pagos_mixtos_json")
    op.drop_column("pedidos", "propina")
    op.drop_column("mesas", "zona")
    op.drop_column("promociones", "hora_fin")
    op.drop_column("promociones", "hora_inicio")
    op.drop_column("promociones", "dias_semana")
