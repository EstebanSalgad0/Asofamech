"""Estructura clinica PA-ASO-001 en los casos

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-16

Añade a `cases` el codigo editorial del caso y el JSON con el formato
PA-ASO-001 (ver app/case_structure.py). Los casos existentes quedan con
structured_json NULL y siguen renderizandose desde `body`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("case_code", sa.String(60), nullable=True))
    op.add_column("cases", sa.Column("structured_json", sa.JSON, nullable=True))
    op.create_index("ix_cases_case_code", "cases", ["case_code"])


def downgrade() -> None:
    op.drop_index("ix_cases_case_code", table_name="cases")
    op.drop_column("cases", "structured_json")
    op.drop_column("cases", "case_code")
