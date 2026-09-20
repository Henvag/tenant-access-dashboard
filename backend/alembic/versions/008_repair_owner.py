"""Repair tenants.owner_user_id — 007 backfill saw zero users under FORCE RLS.

Revision ID: 008_repair_owner
Revises: 007_tenant_owner
Create Date: 2026-03-20
"""

from typing import Sequence, Union

from alembic import op

revision: str = "008_repair_owner"
down_revision: Union[str, None] = "007_tenant_owner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FORCE RLS hides all users rows when app.tenant_id is unset — including
    # from the table owner — so the 007 backfill never matched anyone.
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE tenants t
        SET owner_user_id = u.id
        FROM (
            SELECT DISTINCT ON (tenant_id) id, tenant_id
            FROM users
            WHERE role = 'admin'
            ORDER BY tenant_id, id
        ) u
        WHERE t.id = u.tenant_id
          AND t.owner_user_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE tenants t
        SET owner_user_id = u.id
        FROM (
            SELECT DISTINCT ON (tenant_id) id, tenant_id
            FROM users
            ORDER BY tenant_id, id
        ) u
        WHERE t.id = u.tenant_id
          AND t.owner_user_id IS NULL
        """
    )
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    pass
