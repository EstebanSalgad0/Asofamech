"""Anotaciones docentes sobre imagenes

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-17

Marcadores de texto sobre una region de una imagen del visor, sin relacion con
HistopathologySession ni con el clasificador CONCH/CAMELYON: sirven para que
un docente senale "esto es un linfocito" sobre laminas que no deben analizarse
con IA.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "image_annotations",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "image_id", sa.Integer(),
            sa.ForeignKey("medical_images.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("roi", sa.JSON, nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_image_annotations_image_id", "image_annotations", ["image_id"])


def downgrade() -> None:
    op.drop_index("ix_image_annotations_image_id", table_name="image_annotations")
    op.drop_table("image_annotations")
