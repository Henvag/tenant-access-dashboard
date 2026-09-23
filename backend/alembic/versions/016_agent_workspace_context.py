"""Let an agent answer questions about the workspace it belongs to.

Revision ID: 016_agent_workspace_context
Revises: 015_ai_agents
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016_agent_workspace_context"
down_revision: Union[str, None] = "015_ai_agents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "team_agents",
        sa.Column(
            "workspace_context",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("team_agents", "workspace_context")
