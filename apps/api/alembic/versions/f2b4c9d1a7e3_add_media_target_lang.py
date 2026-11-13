"""add media target_lang

Revision ID: f2b4c9d1a7e3
Revises: c5d2a8e61f37
Create Date: 2026-11-13 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2b4c9d1a7e3"
down_revision: Union[str, None] = "c5d2a8e61f37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "media",
        sa.Column("target_lang", sa.String(length=10), server_default="hi", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("media", "target_lang")
