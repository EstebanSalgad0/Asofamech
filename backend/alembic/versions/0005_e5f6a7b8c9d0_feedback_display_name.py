"""Add display_name to usability_feedback

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-31 20:00:00.000000

Campo opcional para que el estudiante indique su nombre en la evaluacion.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "usability_feedback",
        sa.Column("display_name", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("usability_feedback", "display_name")
