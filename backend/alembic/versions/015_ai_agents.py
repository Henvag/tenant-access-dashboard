"""Turn shared agent links into company AI accounts.

Revision ID: 015_ai_agents
Revises: 014_portal
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "015_ai_agents"
down_revision: Union[str, None] = "014_portal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

POLICY = postgresql.ENUM(
    "everyone",
    "admins",
    "assigned",
    name="oauth_access_policy",
    create_type=False,
)


def upgrade() -> None:
    # Bookmark rows cannot become API agents. RLS would hide them from the
    # migration role, so turn it off for this rewrite.
    op.execute("ALTER TABLE team_agents NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE team_agents DISABLE ROW LEVEL SECURITY")
    op.execute("DELETE FROM team_agents")
    op.drop_column("team_agents", "url")
    op.add_column("team_agents", sa.Column("provider", sa.String(length=32), nullable=False))
    op.add_column("team_agents", sa.Column("model", sa.String(length=80), nullable=False))
    op.add_column("team_agents", sa.Column("secret", sa.Text(), nullable=False))
    op.add_column("team_agents", sa.Column("key_hint", sa.String(length=8), nullable=False))
    op.add_column(
        "team_agents",
        sa.Column(
            "access_policy",
            POLICY,
            nullable=False,
            server_default="everyone",
        ),
    )
    op.execute("ALTER TABLE team_agents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE team_agents FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE team_agents NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE team_agents DISABLE ROW LEVEL SECURITY")
    op.execute("DELETE FROM team_agents")
    op.drop_column("team_agents", "access_policy")
    op.drop_column("team_agents", "key_hint")
    op.drop_column("team_agents", "secret")
    op.drop_column("team_agents", "model")
    op.drop_column("team_agents", "provider")
    op.add_column("team_agents", sa.Column("url", sa.String(length=2048), nullable=True))
    op.execute("ALTER TABLE team_agents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE team_agents FORCE ROW LEVEL SECURITY")
