"""Create disease_categories table

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-08-27

Catalogo de enfermedades de Imagenes IA (icono, titulo, descripcion y
palabras clave), antes hardcodeado en el frontend. Se siembra con las
categorias que ya existian para no perder nada al migrar (ver
app/seeds/disease_categories_loader.py).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, None] = "f8a9b0c1d2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "disease_categories",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("key", sa.String(60), nullable=False, unique=True, index=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("icon", sa.String(16), nullable=False, server_default="🧫"),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("keywords", sa.JSON, nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_disease_categories_created_by"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("disease_categories")
