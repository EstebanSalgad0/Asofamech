"""Agrupar entregas de informe por batch (multi-rubrica)

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-08-18

Un mismo archivo puede evaluarse contra varias rubricas a la vez; cada
combinacion (archivo, rubrica) sigue siendo su propia fila con su propia
evaluacion, pero ahora comparten `batch_id` para que la interfaz las agrupe
como un solo informe con varios resultados.

Las filas existentes (todas de un envio con una sola rubrica) reciben un
batch_id propio y distinto cada una: no comparten archivo con ninguna otra
fila, asi que agruparlas junto a otras seria incorrecto.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "report_submissions",
        sa.Column("batch_id", sa.String(36), nullable=True),
    )

    connection = op.get_bind()
    submission_ids = [row[0] for row in connection.execute(sa.text("SELECT id FROM report_submissions"))]
    for submission_id in submission_ids:
        connection.execute(
            sa.text("UPDATE report_submissions SET batch_id = :batch_id WHERE id = :id"),
            {"batch_id": str(uuid.uuid4()), "id": submission_id},
        )

    op.alter_column("report_submissions", "batch_id", nullable=False)
    op.create_index("ix_report_submissions_batch_id", "report_submissions", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_report_submissions_batch_id", table_name="report_submissions")
    op.drop_column("report_submissions", "batch_id")
