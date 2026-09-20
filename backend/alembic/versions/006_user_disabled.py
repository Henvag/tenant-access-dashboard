"""Add users.disabled_at and audit event types for enable/disable.

Revision ID: 006_user_disabled
Revises: 005_audit_failures
Create Date: 2026-03-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_user_disabled"
down_revision: Union[str, None] = "005_audit_failures"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE audit_event_type ADD VALUE 'user_disabled';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE audit_event_type ADD VALUE 'user_enabled';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_column("users", "disabled_at")
    # Postgres cannot remove enum values safely; leave user_disabled / user_enabled.
