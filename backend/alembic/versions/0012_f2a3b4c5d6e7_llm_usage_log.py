"""Registro de consumo del LLM (tokens y latencia por llamada)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-12

Una fila por llamada al proveedor generativo. Sin user_id: anónimo por diseño,
coherente con la política del módulo de encuestas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_log",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("feature", sa.String(80), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_kind", sa.String(60), nullable=True),
        sa.Column("estimated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_llm_usage_log_occurred_at", "llm_usage_log", ["occurred_at"])
    op.create_index("ix_llm_usage_log_provider", "llm_usage_log", ["provider"])
    op.create_index("ix_llm_usage_log_model", "llm_usage_log", ["model"])
    op.create_index("ix_llm_usage_log_feature", "llm_usage_log", ["feature"])
    op.create_index("ix_llm_usage_log_success", "llm_usage_log", ["success"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_log_success", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_feature", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_model", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_provider", table_name="llm_usage_log")
    op.drop_index("ix_llm_usage_log_occurred_at", table_name="llm_usage_log")
    op.drop_table("llm_usage_log")
