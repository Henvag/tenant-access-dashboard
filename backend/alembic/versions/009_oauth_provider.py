"""OIDC provider: signing keys, registered apps, grants, auth codes, audit details.

Revision ID: 009_oauth_provider
Revises: 008_repair_owner
Create Date: 2026-09-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_oauth_provider"
down_revision: Union[str, None] = "008_repair_owner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = ("oauth_clients", "app_grants", "oauth_codes")

TENANT_PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"


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


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE oauth_access_policy AS ENUM ('everyone', 'admins', 'assigned');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    access_policy = postgresql.ENUM(
        "everyone", "admins", "assigned", name="oauth_access_policy", create_type=False
    )

    for value in (
        "app_created",
        "app_deleted",
        "app_access_granted",
        "app_access_revoked",
        "app_login",
        "app_login_denied",
    ):
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
        "audit_events",
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "signing_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kid", sa.String(length=64), nullable=False),
        sa.Column("private_pem", sa.Text(), nullable=False),
        sa.Column("public_pem", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signing_keys")),
        sa.UniqueConstraint("kid", name=op.f("uq_signing_keys_kid")),
    )

    op.create_table(
        "oauth_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("client_secret_hash", sa.String(length=128), nullable=False),
        sa.Column("redirect_uris", postgresql.ARRAY(sa.String(length=2048)), nullable=False),
        sa.Column("launch_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "access_policy", access_policy, nullable=False, server_default="everyone"
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_oauth_clients_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_oauth_clients_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_clients")),
        sa.UniqueConstraint("client_id", name=op.f("uq_oauth_clients_client_id")),
    )
    op.create_index(op.f("ix_oauth_clients_tenant_id"), "oauth_clients", ["tenant_id"])

    # Public index so /oauth/token can resolve a tenant before scoping RLS. No secrets.
    op.create_table(
        "oauth_client_lookup",
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_oauth_client_lookup_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("client_id", name=op.f("pk_oauth_client_lookup")),
    )

    op.create_table(
        "app_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_pk", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_app_grants_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_pk"],
            ["oauth_clients.id"],
            name=op.f("fk_app_grants_client_pk_oauth_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_app_grants_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name=op.f("fk_app_grants_granted_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_grants")),
        sa.UniqueConstraint("client_pk", "user_id", name="uq_app_grants_client_user"),
    )
    op.create_index(op.f("ix_app_grants_tenant_id"), "app_grants", ["tenant_id"])
    op.create_index(op.f("ix_app_grants_client_pk"), "app_grants", ["client_pk"])
    op.create_index(op.f("ix_app_grants_user_id"), "app_grants", ["user_id"])

    op.create_table(
        "oauth_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_pk", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("redirect_uri", sa.String(length=2048), nullable=False),
        sa.Column("scope", sa.String(length=256), nullable=False),
        sa.Column("nonce", sa.String(length=256), nullable=True),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("code_challenge_method", sa.String(length=8), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_oauth_codes_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_pk"],
            ["oauth_clients.id"],
            name=op.f("fk_oauth_codes_client_pk_oauth_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_oauth_codes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_codes")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_oauth_codes_code_hash")),
    )
    op.create_index(op.f("ix_oauth_codes_tenant_id"), "oauth_codes", ["tenant_id"])

    for table in RLS_TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in RLS_TABLES:
        _disable_rls(table)
    op.drop_index(op.f("ix_oauth_codes_tenant_id"), table_name="oauth_codes")
    op.drop_table("oauth_codes")
    op.drop_index(op.f("ix_app_grants_user_id"), table_name="app_grants")
    op.drop_index(op.f("ix_app_grants_client_pk"), table_name="app_grants")
    op.drop_index(op.f("ix_app_grants_tenant_id"), table_name="app_grants")
    op.drop_table("app_grants")
    op.drop_table("oauth_client_lookup")
    op.drop_index(op.f("ix_oauth_clients_tenant_id"), table_name="oauth_clients")
    op.drop_table("oauth_clients")
    op.drop_table("signing_keys")
    op.drop_column("audit_events", "details")
    op.execute("DROP TYPE IF EXISTS oauth_access_policy")
    # Postgres cannot remove enum values safely; app_* audit types remain.
