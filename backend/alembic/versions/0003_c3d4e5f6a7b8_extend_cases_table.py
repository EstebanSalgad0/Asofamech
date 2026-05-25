"""Extend cases table with clinical fields, status, timestamps and FKs

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-24 12:00:00.000000

Adds: clinical_context, learning_objectives, difficulty, topic,
      image_id (FK), sct_test_id (FK), created_by (FK),
      status (draft/published/archived), created_at, updated_at.
Existing rows get status='published' to preserve current visibility.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("clinical_context", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("learning_objectives", sa.Text(), nullable=True))
    op.add_column("cases", sa.Column("difficulty", sa.String(50), nullable=True))
    op.add_column("cases", sa.Column("topic", sa.String(200), nullable=True))
    op.add_column(
        "cases",
        sa.Column(
            "image_id",
            sa.Integer(),
            sa.ForeignKey("medical_images.id", name="fk_cases_image_id"),
            nullable=True,
        ),
    )
    op.add_column(
        "cases",
        sa.Column(
            "sct_test_id",
            sa.Integer(),
            sa.ForeignKey("sct_tests.id", name="fk_cases_sct_test_id"),
            nullable=True,
        ),
    )
    op.add_column(
        "cases",
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_cases_created_by"),
            nullable=True,
        ),
    )
    op.add_column(
        "cases",
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
    )
    op.add_column(
        "cases",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.text("NOW()"),
        ),
    )
    op.add_column(
        "cases",
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=True,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_cases_status", "cases", ["status"])
    op.create_index("ix_cases_topic", "cases", ["topic"])
    # Existing cases become published so they remain visible
    op.execute("UPDATE cases SET status = 'published'")


def downgrade() -> None:
    op.drop_index("ix_cases_topic", table_name="cases")
    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_column("cases", "updated_at")
    op.drop_column("cases", "created_at")
    op.drop_column("cases", "status")
    op.drop_column("cases", "created_by")
    op.drop_column("cases", "sct_test_id")
    op.drop_column("cases", "image_id")
    op.drop_column("cases", "topic")
    op.drop_column("cases", "difficulty")
    op.drop_column("cases", "learning_objectives")
    op.drop_column("cases", "clinical_context")
