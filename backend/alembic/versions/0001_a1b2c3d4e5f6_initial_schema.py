"""Initial schema: all ASOFAMECH tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-05-23 00:00:00.000000

NOTE: For databases that already exist (pre-Alembic), do NOT run upgrade —
instead stamp them:
    alembic stamp head
Future migrations will then be applied normally.

For a fresh database:
    alembic upgrade head
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Must match rag_utils.EMBEDDING_DIMENSIONS
EMBEDDING_DIMENSIONS = 384


def upgrade() -> None:
    # pgvector extension — required for document_vector_embeddings
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------ users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("email", sa.String(200), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("role", sa.String(50), server_default="estudiante"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("account_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column(
            "approved_by",
            sa.Integer,
            sa.ForeignKey("users.id", name="fk_users_approved_by"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
    )

    # ---------------------------------------------------------- medical_images
    op.create_table(
        "medical_images",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("filename", sa.String(200), unique=True, nullable=False),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("pathology_type", sa.String(200), nullable=True),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("dzi_path", sa.String(500), nullable=True),
        sa.Column(
            "uploaded_by",
            sa.Integer,
            sa.ForeignKey("users.id", name="fk_medical_images_uploaded_by"),
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
    )

    # --------------------------------------------------------------- cases
    op.create_table(
        "cases",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
    )

    # ------------------------------------------------------------ documents
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", sa.String(200), nullable=True),
        sa.Column("source", sa.String(500), nullable=True),
        sa.Column("document_type", sa.String(50), nullable=False, server_default="text"),
        sa.Column(
            "uploaded_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "created_by",
            sa.Integer,
            sa.ForeignKey("users.id", name="fk_documents_created_by"),
            nullable=True,
            index=True,
        ),
        sa.Column("indexing_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("indexing_error", sa.Text, nullable=True),
        sa.Column("chunk_size", sa.Integer, nullable=False, server_default="180"),
        sa.Column("chunk_overlap", sa.Integer, nullable=False, server_default="40"),
    )

    # ------------------------------------------------------- document_chunks
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("documents.id", name="fk_document_chunks_document_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.JSON, nullable=False),
        sa.Column(
            "embedding_provider",
            sa.String(160),
            nullable=False,
            server_default="local-hashing",
        ),
        sa.Column("token_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
    )

    # ------------------------------------------------------------ chat_logs
    op.create_table(
        "chat_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("user_id", sa.String(50), nullable=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("rag_sources", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
    )

    # ------------------------------------------------------- ai_configurations
    op.create_table(
        "ai_configurations",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("key", sa.String(120), unique=True, nullable=False, index=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("value_type", sa.String(40), nullable=False, server_default="string"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("NOW()")),
    )

    # ------------------------------------------------------ email_templates
    op.create_table(
        "email_templates",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("NOW()")),
    )

    # ---------------------------------------------------------- sct_tests
    op.create_table(
        "sct_tests",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("difficulty", sa.String(50), nullable=False),
        sa.Column("focus", sa.String(200), nullable=False),
        sa.Column("num_items", sa.Integer, nullable=False),
        sa.Column("items_json", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("NOW()")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
    )

    # --------------------------------------------------------- heatmap_jobs
    op.create_table(
        "heatmap_jobs",
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("trace_id", sa.String(36), nullable=False, index=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", name="fk_heatmap_jobs_user_id"),
            nullable=True,
            index=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("processed_tiles", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tiles", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("failed_at", sa.DateTime, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("request_json", sa.JSON, nullable=True),
        sa.Column("result_json", sa.JSON, nullable=True),
        sa.Column("worker_limit", sa.Integer, nullable=False, server_default="1"),
    )

    # -------------------------------------------------------- sct_attempts
    op.create_table(
        "sct_attempts",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "test_id",
            sa.Integer,
            sa.ForeignKey("sct_tests.id", name="fk_sct_attempts_test_id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", name="fk_sct_attempts_user_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("answers_json", sa.JSON, nullable=False),
        sa.Column("score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("correct_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_items", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column(
            "completed_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # ------------------------------------------------ histopathology_sessions
    op.create_table(
        "histopathology_sessions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("trace_id", sa.String(36), unique=True, nullable=False, index=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", name="fk_histopathology_sessions_user_id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "image_id",
            sa.Integer,
            sa.ForeignKey("medical_images.id", name="fk_histopathology_sessions_image_id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "analyzed_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("roi_1", sa.JSON, nullable=False),
        sa.Column("roi_2", sa.JSON, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("clase", sa.String(50), nullable=True),
        sa.Column("confidence", sa.JSON, nullable=True),
        sa.Column("probabilities", sa.JSON, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("roi_quality_metrics", sa.JSON, nullable=True),
        sa.Column("warning", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
    )

    # ---------------------------------------------- histopathology_corrections
    op.create_table(
        "histopathology_corrections",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "session_id",
            sa.Integer,
            sa.ForeignKey(
                "histopathology_sessions.id",
                name="fk_histopathology_corrections_session_id",
            ),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("trace_id", sa.String(36), nullable=False, index=True),
        sa.Column("image_id", sa.Integer, nullable=False, index=True),
        sa.Column(
            "docente_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", name="fk_histopathology_corrections_docente"),
            nullable=False,
        ),
        sa.Column("docente_label", sa.String(80), nullable=False),
        sa.Column("docente_note", sa.Text, nullable=True),
        sa.Column(
            "include_in_dataset",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "corrected_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # --------------------------------- document_vector_embeddings (pgvector)
    # Uses the vector type — created via raw SQL to avoid needing the pgvector
    # Python package as a SQLAlchemy type extension.
    op.execute(
        f"""
        CREATE TABLE document_vector_embeddings (
            id          SERIAL PRIMARY KEY,
            chunk_id    INTEGER UNIQUE REFERENCES document_chunks(id) ON DELETE CASCADE,
            document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
            embedding   vector({EMBEDDING_DIMENSIONS}) NOT NULL,
            provider    VARCHAR(160) NOT NULL,
            updated_at  TIMESTAMP DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_document_vector_embeddings_document_id
        ON document_vector_embeddings(document_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS document_vector_embeddings CASCADE")
    op.drop_table("histopathology_corrections")
    op.drop_table("histopathology_sessions")
    op.drop_table("sct_attempts")
    op.drop_table("heatmap_jobs")
    op.drop_table("sct_tests")
    op.drop_table("email_templates")
    op.drop_table("ai_configurations")
    op.drop_table("chat_logs")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("cases")
    op.drop_table("medical_images")
    op.drop_table("users")
