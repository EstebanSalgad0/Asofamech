"""add case_links table

Recursos externos asociados a un caso clinico: bibliografia complementaria,
guias, articulos y actividades interactivas (Wooclap). Solo se almacena el
enlace; la plataforma no aloja ni proxifica el contenido remoto.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-07

"""
from alembic import op
import sqlalchemy as sa

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "case_id",
            sa.Integer(),
            sa.ForeignKey("cases.id", ondelete="CASCADE", name="fk_case_links_case_id"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(40), nullable=False, server_default="otro"),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("description", sa.String(400), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_case_links_created_by"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_case_links_id", "case_links", ["id"])
    op.create_index("ix_case_links_case_id", "case_links", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_case_links_case_id", table_name="case_links")
    op.drop_index("ix_case_links_id", table_name="case_links")
    op.drop_table("case_links")
