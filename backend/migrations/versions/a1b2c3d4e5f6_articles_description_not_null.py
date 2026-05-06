"""articles description not null

Revision ID: a1b2c3d4e5f6
Revises: cfe2a836394a
Create Date: 2026-05-07 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "cfe2a836394a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("articles", "description", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.alter_column("articles", "description", existing_type=sa.Text(), nullable=True)
