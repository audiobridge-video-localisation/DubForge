"""merge translation_source and artifact speedup

Revision ID: c5d2a8e61f37
Revises: a41c9d7e2b10, b7e3f1c94d20
Create Date: 2026-11-12 12:00:00.000000

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "c5d2a8e61f37"
down_revision: Union[str, Sequence[str], None] = ("a41c9d7e2b10", "b7e3f1c94d20")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
