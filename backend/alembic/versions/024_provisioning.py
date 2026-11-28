"""Account provisioning: create and deactivate people's accounts in apps (Slack first).

- oauth_clients.provision_*: the app's provisioning token (encrypted) and kind.
- app_accounts: one row per app and email, with the account's id in the app and
  the last result. Tenant data under FORCE RLS.
- provision_outbox: secret-free queue (account id, tenant id, due time), like
  webhook_outbox, so the background worker finds due work without reading
  across tenants.

Revision ID: 024_provisioning
Revises: 023_app_signout
Create Date: 2026-11-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "024_provisioning"
down_revision: Union[str, None] = "023_app_signout"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def _uuid(name: str, **kw) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), **kw)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE audit_event_type ADD VALUE 'app_account_changed';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.add_column("oauth_clients", sa.Column("provision_kind", sa.String(16), nullable=True))
    op.add_column("oauth_clients", sa.Column("provision_secret", sa.Text(), nullable=True))
    op.add_column("oauth_clients", sa.Column("provision_key_hint", sa.String(8), nullable=True))

    op.create_table(
        "app_accounts",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("client_pk", nullable=False),
        _uuid("user_id", nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("remote_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.String(64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_app_accounts_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_pk"], ["oauth_clients.id"],
            name=op.f("fk_app_accounts_client_pk_oauth_clients"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_app_accounts_user_id_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_accounts")),
    )
    op.create_index(op.f("ix_app_accounts_tenant_id"), "app_accounts", ["tenant_id"])
    # Deleted people have an empty address; every other address is one row per app.
    op.create_index(
        "uq_app_accounts_client_email",
        "app_accounts",
        ["client_pk", "email"],
        unique=True,
        postgresql_where=sa.text("email <> ''"),
    )

    op.create_table(
        "provision_outbox",
        _uuid("account_id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["app_accounts.id"],
            name=op.f("fk_provision_outbox_account_id_app_accounts"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_provision_outbox_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("account_id", name=op.f("pk_provision_outbox")),
    )
    op.create_index("ix_provision_outbox_due", "provision_outbox", ["next_attempt_at"])

    op.execute("ALTER TABLE app_accounts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE app_accounts FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY app_accounts_tenant_isolation ON app_accounts
        USING ({TENANT_PREDICATE})
        WITH CHECK ({TENANT_PREDICATE})
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS app_accounts_tenant_isolation ON app_accounts")
    op.drop_index("ix_provision_outbox_due", table_name="provision_outbox")
    op.drop_table("provision_outbox")
    op.drop_index("uq_app_accounts_client_email", table_name="app_accounts")
    op.drop_index(op.f("ix_app_accounts_tenant_id"), table_name="app_accounts")
    op.drop_table("app_accounts")
    op.drop_column("oauth_clients", "provision_key_hint")
    op.drop_column("oauth_clients", "provision_secret")
    op.drop_column("oauth_clients", "provision_kind")
