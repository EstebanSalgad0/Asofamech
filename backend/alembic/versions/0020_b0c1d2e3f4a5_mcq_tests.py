"""Create mcq_tests, mcq_attempts and cases.mcq_test_id

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-08-27

Modulo de Test de alternativas (pregunta + opciones + correcta), paralelo al
SCT: banco de tests, intentos de estudiante, y un vinculo opcional desde
cases igual al que ya existe con sct_test_id.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, None] = "a9b0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcq_tests",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("difficulty", sa.String(50), nullable=True),
        sa.Column("num_items", sa.Integer(), nullable=False),
        sa.Column("items_json", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_mcq_tests_created_by"),
            nullable=True,
        ),
    )

    op.create_table(
        "mcq_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "test_id",
            sa.Integer(),
            sa.ForeignKey("mcq_tests.id", name="fk_mcq_attempts_test_id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_mcq_attempts_user_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("answers_json", sa.JSON, nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )

    op.add_column(
        "cases",
        sa.Column(
            "mcq_test_id",
            sa.Integer(),
            sa.ForeignKey("mcq_tests.id", name="fk_cases_mcq_test_id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("cases", "mcq_test_id")
    op.drop_table("mcq_attempts")
    op.drop_table("mcq_tests")
