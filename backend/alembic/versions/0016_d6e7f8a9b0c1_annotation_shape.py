"""Forma de la anotacion: rectangulo u ovalo

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-08-18

El ovalo se dibuja inscrito en el mismo rectangulo delimitador que ya se
guardaba (`roi`): no hace falta un esquema de coordenadas nuevo, solo saber
como pintarlo. Las filas existentes quedan en 'rect' (su forma actual).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "image_annotations",
        sa.Column("shape", sa.String(20), nullable=False, server_default="rect"),
    )


def downgrade() -> None:
    op.drop_column("image_annotations", "shape")
