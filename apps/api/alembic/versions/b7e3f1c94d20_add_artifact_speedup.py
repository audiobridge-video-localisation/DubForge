"""add artifact speedup

Revision ID: b7e3f1c94d20
Revises: 7620310948d4
Create Date: 2026-11-12 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7e3f1c94d20"
down_revision: Union[str, None] = "7620310948d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "artifacts", sa.Column("speedup", sa.Float(), server_default="1", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("artifacts", "speedup")
