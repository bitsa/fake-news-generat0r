"""initial schema

Revision ID: cfe2a836394a
Revises:
Create Date: 2026-05-06 19:59:32.530280

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.sources import Source

# revision identifiers, used by Alembic.
revision: str = "cfe2a836394a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    source_type = postgresql.ENUM(
        *[s.value for s in Source], name="source_type", create_type=False
    )
    source_type.create(op.get_bind(), checkfirst=False)

    op.create_table(
        "articles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", source_type, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("url", name="uq_articles_url"),
    )

    op.create_index("ix_articles_source", "articles", ["source"])
    op.create_index(
        "ix_articles_published_at",
        "articles",
        [sa.text("published_at DESC NULLS LAST")],
    )

    op.create_table(
        "article_fakes",
        sa.Column(
            "article_id",
            sa.Integer,
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "transform_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("temperature", sa.Double, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "transform_status IN ('pending', 'completed')",
            name="ck_article_fakes_transform_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("article_fakes")
    op.drop_index("ix_articles_published_at", table_name="articles")
    op.drop_index("ix_articles_source", table_name="articles")
    op.drop_table("articles")

    source_type = postgresql.ENUM(
        *[s.value for s in Source], name="source_type", create_type=False
    )
    source_type.drop(op.get_bind(), checkfirst=False)
