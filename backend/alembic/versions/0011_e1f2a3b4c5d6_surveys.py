"""Encuestas de percepción + eliminación de usability_feedback

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-12

- Elimina el módulo antiguo de usability_feedback (tabla + índice).
- Crea 5 tablas para el módulo de encuestas de percepción:
    surveys, survey_items, survey_responses, survey_answers, survey_participation
- Diseño anónimo: survey_responses NO contiene user_id; survey_participation
  liga user↔survey solo para bloquear duplicados, sin clave común con las
  respuestas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Eliminar módulo antiguo
    op.drop_index("ix_usability_feedback_user_id", table_name="usability_feedback")
    op.drop_table("usability_feedback")

    # 2) surveys
    op.create_table(
        "surveys",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("code", sa.String(60), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_surveys_code", "surveys", ["code"], unique=True)

    # 3) survey_items
    op.create_table(
        "survey_items",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "survey_id",
            sa.Integer(),
            sa.ForeignKey("surveys.id", ondelete="CASCADE", name="fk_survey_items_survey_id"),
            nullable=False,
        ),
        sa.Column("section", sa.String(200), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("item_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("item_type", sa.String(20), nullable=False, server_default="likert_1_5"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_survey_items_survey_id", "survey_items", ["survey_id"])

    # 4) survey_responses (sin user_id: anónimo por diseño)
    op.create_table(
        "survey_responses",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "survey_id",
            sa.Integer(),
            sa.ForeignKey("surveys.id", ondelete="CASCADE", name="fk_survey_responses_survey_id"),
            nullable=False,
        ),
        sa.Column("role_at_submission", sa.String(50), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_survey_responses_survey_id", "survey_responses", ["survey_id"])

    # 5) survey_answers
    op.create_table(
        "survey_answers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "response_id",
            sa.Integer(),
            sa.ForeignKey("survey_responses.id", ondelete="CASCADE", name="fk_survey_answers_response_id"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("survey_items.id", ondelete="CASCADE", name="fk_survey_answers_item_id"),
            nullable=False,
        ),
        sa.Column("value_int", sa.Integer(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
    )
    op.create_index("ix_survey_answers_response_id", "survey_answers", ["response_id"])
    op.create_index("ix_survey_answers_item_id", "survey_answers", ["item_id"])

    # 6) survey_participation
    op.create_table(
        "survey_participation",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "survey_id",
            sa.Integer(),
            sa.ForeignKey("surveys.id", ondelete="CASCADE", name="fk_survey_participation_survey_id"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_survey_participation_user_id"),
            nullable=False,
        ),
        sa.Column("participated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("survey_id", "user_id", name="uq_survey_participation_survey_user"),
    )
    op.create_index("ix_survey_participation_survey_id", "survey_participation", ["survey_id"])
    op.create_index("ix_survey_participation_user_id", "survey_participation", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_survey_participation_user_id", table_name="survey_participation")
    op.drop_index("ix_survey_participation_survey_id", table_name="survey_participation")
    op.drop_table("survey_participation")

    op.drop_index("ix_survey_answers_item_id", table_name="survey_answers")
    op.drop_index("ix_survey_answers_response_id", table_name="survey_answers")
    op.drop_table("survey_answers")

    op.drop_index("ix_survey_responses_survey_id", table_name="survey_responses")
    op.drop_table("survey_responses")

    op.drop_index("ix_survey_items_survey_id", table_name="survey_items")
    op.drop_table("survey_items")

    op.drop_index("ix_surveys_code", table_name="surveys")
    op.drop_table("surveys")

    op.create_table(
        "usability_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("role_at_submission", sa.String(50), nullable=False),
        sa.Column("nav_clarity", sa.Integer(), nullable=False),
        sa.Column("viewer_ease", sa.Integer(), nullable=False),
        sa.Column("roi_ease", sa.Integer(), nullable=False),
        sa.Column("ai_clarity", sa.Integer(), nullable=False),
        sa.Column("chatbot_utility", sa.Integer(), nullable=False),
        sa.Column("sct_utility", sa.Integer(), nullable=False),
        sa.Column("observations", sa.Text(), nullable=True),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_usability_feedback_user_id", "usability_feedback", ["user_id"])
