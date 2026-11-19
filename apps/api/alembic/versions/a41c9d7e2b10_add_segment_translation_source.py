"""add segment translation_source

Revision ID: a41c9d7e2b10
Revises: 7620310948d4
Create Date: 2026-11-04 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a41c9d7e2b10"
down_revision: Union[str, None] = "7620310948d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "segments",
        sa.Column(
            "translation_source",
            sa.String(length=20),
            server_default="machine",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("segments", "translation_source")
