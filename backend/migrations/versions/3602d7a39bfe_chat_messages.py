"""chat messages

Revision ID: 3602d7a39bfe
Revises: cfe2a836394a
Create Date: 2026-05-07 06:07:56.984212

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3602d7a39bfe"
down_revision: str | None = "cfe2a836394a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "article_id",
            sa.Integer,
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "is_error",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_chat_messages_role",
        ),
    )

    op.create_index(
        "ix_chat_messages_article_id_created_at",
        "chat_messages",
        ["article_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chat_messages_article_id_created_at",
        table_name="chat_messages",
    )
    op.drop_table("chat_messages")
