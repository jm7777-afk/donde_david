"""Add archivos_media table for database-backed image persistence.

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b9
Create Date: 2026-11-28 08:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c0"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "archivos_media",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("nombre_archivo", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("tamano_bytes", sa.Integer(), nullable=False),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_archivos_media_id", "archivos_media", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_archivos_media_id", table_name="archivos_media")
    op.drop_table("archivos_media")
