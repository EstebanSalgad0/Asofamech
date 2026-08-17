"""Revisor de informes por rubrica

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-16

Tres tablas: la rubrica que define los criterios, la entrega del estudiante con
el texto ya extraido del documento, y la evaluacion generada por el modelo. La
evaluacion nace con `released` en false: no llega al estudiante hasta que un
docente la publica.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rubrics",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_filename", sa.String(200), nullable=True),
        sa.Column("criteria_json", sa.JSON, nullable=False),
        sa.Column("bands_json", sa.JSON, nullable=True),
        sa.Column("max_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("guidance", sa.Text(), nullable=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_rubrics_case_id", "rubrics", ["case_id"])

    op.create_table(
        "report_submissions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("rubric_id", sa.Integer(), sa.ForeignKey("rubrics.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("stored_filename", sa.String(200), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_report_submissions_rubric_id", "report_submissions", ["rubric_id"])
    op.create_index("ix_report_submissions_case_id", "report_submissions", ["case_id"])
    op.create_index("ix_report_submissions_user_id", "report_submissions", ["user_id"])

    op.create_table(
        "report_evaluations",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "submission_id",
            sa.Integer(),
            sa.ForeignKey("report_submissions.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("total_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("band", sa.String(80), nullable=True),
        sa.Column("criteria_json", sa.JSON, nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("strengths", sa.JSON, nullable=True),
        sa.Column("improvements", sa.JSON, nullable=True),
        sa.Column("provider", sa.String(40), nullable=True),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.Column("released", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("released_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("teacher_note", sa.Text(), nullable=True),
        sa.Column("teacher_score", sa.Float(), nullable=True),
    )
    op.create_index("ix_report_evaluations_submission_id", "report_evaluations", ["submission_id"])


def downgrade() -> None:
    op.drop_index("ix_report_evaluations_submission_id", table_name="report_evaluations")
    op.drop_table("report_evaluations")
    op.drop_index("ix_report_submissions_user_id", table_name="report_submissions")
    op.drop_index("ix_report_submissions_case_id", table_name="report_submissions")
    op.drop_index("ix_report_submissions_rubric_id", table_name="report_submissions")
    op.drop_table("report_submissions")
    op.drop_index("ix_rubrics_case_id", table_name="rubrics")
    op.drop_table("rubrics")
