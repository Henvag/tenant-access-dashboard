"""Verified company domains, sign-in policy, outbound webhooks.

- tenant_domains: extra domains a company proves with a DNS TXT record. Read
  during sign-in before any tenant is known, so like `tenants` it has no RLS;
  the API filters by tenant_id explicitly. It holds no secrets (the token is
  published in DNS anyway).
- tenants.require_managed_accounts: refuse personal Google accounts that use
  the company address, so only Google Workspace / Entra accounts get in.
- webhook_endpoints / webhook_deliveries: tenant data under FORCE RLS.
- webhook_outbox: secret-free queue (delivery id, tenant id, due time) so the
  background sender can find due work without reading across tenants, then
  sets the tenant context before it loads the delivery.

Revision ID: 020_domains_webhooks
Revises: 019_personal_workspaces
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "020_domains_webhooks"
down_revision: Union[str, None] = "019_personal_workspaces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"

NEW_EVENT_TYPES = (
    "audit_exported",
    "domain_added",
    "domain_verified",
    "domain_removed",
    "sign_in_policy_changed",
    "webhook_created",
    "webhook_deleted",
)


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON {table}
        USING ({TENANT_PREDICATE})
        WITH CHECK ({TENANT_PREDICATE})
        """
    )


def _disable_rls(table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def _uuid(name: str, **kw) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), **kw)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    for value in NEW_EVENT_TYPES:
        op.execute(
            f"""
            DO $$ BEGIN
                ALTER TYPE audit_event_type ADD VALUE '{value}';
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )

    op.add_column(
        "tenants",
        sa.Column(
            "require_managed_accounts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "tenant_domains",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("domain", sa.String(length=253), nullable=False),
        sa.Column("verification_token", sa.String(length=64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("created_by", nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_tenant_domains_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name=op.f("fk_tenant_domains_created_by_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tenant_domains")),
        sa.UniqueConstraint("tenant_id", "domain", name="uq_tenant_domains_tenant_domain"),
        sa.CheckConstraint("domain = lower(domain)", name="ck_tenant_domains_lowercase"),
    )
    op.create_index(op.f("ix_tenant_domains_tenant_id"), "tenant_domains", ["tenant_id"])
    # A domain can be verified by one company only.
    op.create_index(
        "uq_tenant_domains_verified_domain",
        "tenant_domains",
        ["domain"],
        unique=True,
        postgresql_where=sa.text("verified_at IS NOT NULL"),
    )

    op.create_table(
        "webhook_endpoints",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("secret_hint", sa.String(length=8), nullable=False),
        # NULL = every event type.
        sa.Column("event_types", postgresql.JSONB(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        _uuid("created_by", nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_webhook_endpoints_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name=op.f("fk_webhook_endpoints_created_by_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_endpoints")),
    )
    op.create_index(op.f("ix_webhook_endpoints_tenant_id"), "webhook_endpoints", ["tenant_id"])

    op.create_table(
        "webhook_deliveries",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("endpoint_id", nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(length=255), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_webhook_deliveries_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["endpoint_id"], ["webhook_endpoints.id"],
            name=op.f("fk_webhook_deliveries_endpoint_id_webhook_endpoints"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_deliveries")),
    )
    op.create_index(
        "ix_webhook_deliveries_endpoint_created",
        "webhook_deliveries",
        ["endpoint_id", "created_at"],
    )
    op.create_index(op.f("ix_webhook_deliveries_tenant_id"), "webhook_deliveries", ["tenant_id"])

    op.create_table(
        "webhook_outbox",
        _uuid("delivery_id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["delivery_id"], ["webhook_deliveries.id"],
            name=op.f("fk_webhook_outbox_delivery_id_webhook_deliveries"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_webhook_outbox_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("delivery_id", name=op.f("pk_webhook_outbox")),
    )
    op.create_index("ix_webhook_outbox_due", "webhook_outbox", ["next_attempt_at"])

    _enable_rls("webhook_endpoints")
    _enable_rls("webhook_deliveries")


def downgrade() -> None:
    _disable_rls("webhook_deliveries")
    _disable_rls("webhook_endpoints")
    op.drop_table("webhook_outbox")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_endpoints")
    op.drop_index("uq_tenant_domains_verified_domain", table_name="tenant_domains")
    op.drop_table("tenant_domains")
    op.drop_column("tenants", "require_managed_accounts")
    # Postgres cannot drop enum values; the new audit types stay.
