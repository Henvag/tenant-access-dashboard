"""Logout URL on apps, team logo, and shared agent links.

Revision ID: 014_portal
Revises: 013_billing
Create Date: 2026-09-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "014_portal"
down_revision: Union[str, None] = "013_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.add_column(
        "oauth_clients",
        sa.Column("backchannel_logout_uri", sa.String(length=2048), nullable=True),
    )
    op.add_column("tenants", sa.Column("logo_bytes", sa.LargeBinary(), nullable=True))
    op.add_column("tenants", sa.Column("logo_media_type", sa.String(length=64), nullable=True))
    op.create_table(
        "team_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_agents_tenant_id", "team_agents", ["tenant_id"])
    op.execute("ALTER TABLE team_agents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE team_agents FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY team_agents_tenant_isolation ON team_agents
        USING ({TENANT_PREDICATE})
        WITH CHECK ({TENANT_PREDICATE})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS team_agents_tenant_isolation ON team_agents")
    op.execute("ALTER TABLE team_agents NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE team_agents DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_team_agents_tenant_id", table_name="team_agents")
    op.drop_table("team_agents")
    op.drop_column("tenants", "logo_media_type")
    op.drop_column("tenants", "logo_bytes")
    op.drop_column("oauth_clients", "backchannel_logout_uri")
