"""add case_images table

Imagenes ilustrativas de casos clinicos (radiografia, TAC, fotografia clinica).
Piscina separada de medical_images, que es la de laminas histopatologicas
analizables por el clasificador.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-31

"""
from alembic import op
import sqlalchemy as sa

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("cases.id", ondelete="CASCADE", name="fk_case_images_case_id"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("original_filename", sa.String(200), nullable=False),
        sa.Column("caption", sa.String(300), nullable=True),
        sa.Column("modality", sa.String(80), nullable=True),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "uploaded_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_case_images_uploaded_by"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_images_id", "case_images", ["id"])
    op.create_index("ix_case_images_case_id", "case_images", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_case_images_case_id", table_name="case_images")
    op.drop_index("ix_case_images_id", table_name="case_images")
    op.drop_table("case_images")
