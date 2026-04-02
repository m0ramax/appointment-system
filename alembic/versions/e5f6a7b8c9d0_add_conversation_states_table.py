"""add conversation_states table

Revision ID: e5f6a7b8c9d0
Revises: 38706968f3d8
Create Date: 2026-04-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "38706968f3d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_states (
            phone      VARCHAR      PRIMARY KEY,
            state      VARCHAR      NOT NULL DEFAULT 'INICIO',
            context    JSONB,
            updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversation_states;")
