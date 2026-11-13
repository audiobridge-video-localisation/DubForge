"""add media voice_gender preference

Revision ID: e1a2b3c4d5f6
Revises: c5d2a8e61f37
Create Date: 2026-11-13 10:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, None] = "c5d2a8e61f37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "media",
        sa.Column("voice_gender", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("media", "voice_gender")
