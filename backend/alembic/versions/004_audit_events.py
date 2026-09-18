"""Tenant-scoped sign-in audit events with RLS.

Revision ID: 004_audit_events
Revises: 003_idp_subjects
Create Date: 2026-03-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_audit_events"
down_revision: Union[str, None] = "003_idp_subjects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

audit_event_type = sa.Enum("login", name="audit_event_type")


def upgrade() -> None:
    audit_event_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("event_type", audit_event_type, nullable=False),
        sa.Column(
            "idp",
            postgresql.ENUM("google", "microsoft", name="identity_provider", create_type=False),
            nullable=False,
        ),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_audit_events_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_audit_events_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(op.f("ix_audit_events_tenant_id"), "audit_events", ["tenant_id"])
    op.create_index(
        "ix_audit_events_tenant_created",
        "audit_events",
        ["tenant_id", "created_at"],
    )

    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_events_tenant_isolation ON audit_events
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS audit_events_tenant_isolation ON audit_events")
    op.execute("ALTER TABLE audit_events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_audit_events_tenant_created", table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_tenant_id"), table_name="audit_events")
    op.drop_table("audit_events")
    audit_event_type.drop(op.get_bind(), checkfirst=True)
