"""Add login_failed audit events and error_code.

Revision ID: 005_audit_failures
Revises: 004_audit_events
Create Date: 2026-03-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_audit_failures"
down_revision: Union[str, None] = "004_audit_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE audit_event_type ADD VALUE 'login_failed';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.add_column(
        "audit_events",
        sa.Column("error_code", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_events", "error_code")
    # Postgres cannot remove an enum value safely; leave login_failed in place.
