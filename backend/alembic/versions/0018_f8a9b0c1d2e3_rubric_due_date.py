"""Fecha de entrega en rubricas

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-08-18

Pasada esta fecha, la rubrica deja de aceptar entregas nuevas de estudiantes.
Sin fecha (NULL, el valor de todas las rubricas existentes), queda abierta
indefinidamente como hasta ahora.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rubrics", sa.Column("due_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("rubrics", "due_at")
