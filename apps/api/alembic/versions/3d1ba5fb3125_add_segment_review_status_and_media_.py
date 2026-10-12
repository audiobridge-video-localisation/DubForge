"""add segment review status and media ready for dubbing

Revision ID: 3d1ba5fb3125
Revises: 765aeabb8ea0
Create Date: 2026-10-06 15:04:59.415485

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3d1ba5fb3125"
down_revision: Union[str, None] = "765aeabb8ea0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "media",
        sa.Column(
            "ready_for_dubbing", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.add_column(
        "segments",
        sa.Column("review_status", sa.String(length=20), nullable=False, server_default="pending"),
    )


def downgrade() -> None:
    op.drop_column("segments", "review_status")
    op.drop_column("media", "ready_for_dubbing")
