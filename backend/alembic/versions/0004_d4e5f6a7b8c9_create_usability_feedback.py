"""Create usability_feedback table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-24 14:00:00.000000

One row per user (unique constraint on user_id).
Ratings are integers 1-5. No PII exposed in summary endpoints.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usability_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_usability_feedback_user_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("role_at_submission", sa.String(50), nullable=False),
        sa.Column("nav_clarity", sa.Integer(), nullable=False),
        sa.Column("viewer_ease", sa.Integer(), nullable=False),
        sa.Column("roi_ease", sa.Integer(), nullable=False),
        sa.Column("ai_clarity", sa.Integer(), nullable=False),
        sa.Column("chatbot_utility", sa.Integer(), nullable=False),
        sa.Column("sct_utility", sa.Integer(), nullable=False),
        sa.Column("observations", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_usability_feedback_user_id", "usability_feedback", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_usability_feedback_user_id", table_name="usability_feedback")
    op.drop_table("usability_feedback")
