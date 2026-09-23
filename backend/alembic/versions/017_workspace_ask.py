"""Free Gemini Ask lives on the tenant, separate from paid Agents.

Revision ID: 017_workspace_ask
Revises: 016_agent_workspace_context
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017_workspace_ask"
down_revision: Union[str, None] = "016_agent_workspace_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("ask_secret", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("ask_key_hint", sa.String(length=8), nullable=True))
    op.add_column("tenants", sa.Column("ask_model", sa.String(length=80), nullable=True))

    # Move any Gemini agent keys into Ask, then remove Google rows from Agents.
    op.execute("ALTER TABLE team_agents NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE team_agents DISABLE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE tenants AS t
        SET
            ask_secret = a.secret,
            ask_key_hint = a.key_hint,
            ask_model = a.model
        FROM (
            SELECT DISTINCT ON (tenant_id)
                tenant_id, secret, key_hint, model
            FROM team_agents
            WHERE provider = 'google'
            ORDER BY tenant_id, workspace_context DESC, position ASC, created_at ASC
        ) AS a
        WHERE t.id = a.tenant_id
          AND t.ask_secret IS NULL
        """
    )
    op.execute("DELETE FROM team_agents WHERE provider = 'google'")
    op.execute("ALTER TABLE team_agents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE team_agents FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_column("tenants", "ask_model")
    op.drop_column("tenants", "ask_key_hint")
    op.drop_column("tenants", "ask_secret")
