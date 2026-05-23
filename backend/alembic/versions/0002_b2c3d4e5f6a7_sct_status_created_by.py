"""Add status and created_by to sct_tests

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-23 12:00:00.000000

status values: draft | published | archived
Existing tests are set to 'published' to preserve current visibility.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sct_tests",
        sa.Column("status", sa.String(20), nullable=False, server_default="published"),
    )
    op.add_column(
        "sct_tests",
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_sct_tests_created_by"),
            nullable=True,
        ),
    )
    op.create_index("ix_sct_tests_status", "sct_tests", ["status"])
    # Ensure all pre-existing tests are published
    op.execute("UPDATE sct_tests SET status = 'published'")


def downgrade() -> None:
    op.drop_index("ix_sct_tests_status", table_name="sct_tests")
    op.drop_column("sct_tests", "created_by")
    op.drop_column("sct_tests", "status")
