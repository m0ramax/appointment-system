"""fix legacy neon missing users appointments

Revision ID: 38706968f3d8
Revises: 5fa5bfbe5cc9
Create Date: 2026-03-06 06:34:58.092811

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "38706968f3d8"
down_revision: Union[str, None] = "5fa5bfbe5cc9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                CREATE TYPE userrole AS ENUM ('CLIENT', 'PROVIDER');
            END IF;
        END$$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR NOT NULL UNIQUE,
            hashed_password VARCHAR NOT NULL,
            role userrole NOT NULL
        );
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'appointmentstatus') THEN
                CREATE TYPE appointmentstatus AS ENUM ('PENDING', 'CONFIRMED', 'CANCELLED', 'COMPLETED');
            END IF;
        END$$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id SERIAL PRIMARY KEY,
            title VARCHAR NOT NULL,
            description VARCHAR NULL,
            date_time TIMESTAMP NOT NULL,
            duration_minutes INTEGER NOT NULL,
            status appointmentstatus NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ NULL,
            client_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_appointments_id ON appointments (id);")


def downgrade() -> None:
    """Downgrade schema."""
    # Safety fix-forward migration for legacy environments.
    pass
