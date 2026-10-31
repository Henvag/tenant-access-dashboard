"""Give Gmail/Outlook tenants a private workspace keyed by the owner's address.

Shared mailbox domains used to work like company domains, so every Gmail user
landed in one tenant whose first member was admin over strangers. Sign-in now
keys those users by their full address; move existing consumer-domain tenants
to their owner's address so the owner keeps their workspace.

Revision ID: 019_personal_workspaces
Revises: 018_ask_flash_lite
Create Date: 2026-10-31
"""

from typing import Sequence, Union

from alembic import op

revision: str = "019_personal_workspaces"
down_revision: Union[str, None] = "018_ask_flash_lite"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Keep in sync with app.domain.CONSUMER_DOMAINS (normalized forms).
_CONSUMER = (
    "gmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "gmx.com",
    "online.no",
)


def upgrade() -> None:
    domains = ", ".join(f"'{d}'" for d in _CONSUMER)
    # Same as 008: FORCE RLS would hide users from a migration role without BYPASSRLS.
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        UPDATE tenants t
        SET workspace_domain = split_part(lower(u.email), '@', 1) || '@' || t.workspace_domain
        FROM users u
        WHERE u.id = t.owner_user_id
          AND t.workspace_domain IN ({domains})
          AND NOT EXISTS (
            SELECT 1 FROM tenants other
            WHERE other.workspace_domain
              = split_part(lower(u.email), '@', 1) || '@' || t.workspace_domain
          )
        """
    )
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute(
        """
        UPDATE tenants t
        SET workspace_domain = split_part(t.workspace_domain, '@', 2)
        FROM (
            -- Only one private workspace per provider can take the shared domain back.
            SELECT DISTINCT ON (split_part(workspace_domain, '@', 2)) id
            FROM tenants
            WHERE workspace_domain LIKE '%@%'
            ORDER BY split_part(workspace_domain, '@', 2), created_at
        ) pick
        WHERE t.id = pick.id
          AND NOT EXISTS (
            SELECT 1 FROM tenants other
            WHERE other.workspace_domain = split_part(t.workspace_domain, '@', 2)
          )
        """
    )
