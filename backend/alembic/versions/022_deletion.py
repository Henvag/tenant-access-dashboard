"""Owners can delete a person or the whole company.

Only a new audit type is needed: deleting a company removes the tenant row and
every table that hangs off it cascades, and deleting a person scrubs their
email, IP and browser from the audit log before the row goes.

Revision ID: 022_deletion
Revises: 021_partner_mode
Create Date: 2026-11-02
"""

from typing import Sequence, Union

from alembic import op

revision: str = "022_deletion"
down_revision: Union[str, None] = "021_partner_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE audit_event_type ADD VALUE 'user_deleted';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def downgrade() -> None:
    # Postgres cannot drop a value from an enum; the unused value is harmless.
    pass
