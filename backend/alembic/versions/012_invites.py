"""Company invite tokens + pending app grants by email.

Revision ID: 012_invites
Revises: 011_restore_oauth_clients
Create Date: 2026-09-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "012_invites"
down_revision: Union[str, None] = "011_restore_oauth_clients"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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
    # Public token → tenant index (no secrets). Unauthenticated landing can resolve
    # ?invite= without setting app.tenant_id first.
    op.create_table(
        "company_invite_tokens",
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_company_invite_tokens_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_company_invite_tokens_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("token", name=op.f("pk_company_invite_tokens")),
        sa.UniqueConstraint("tenant_id", name="uq_company_invite_tokens_tenant"),
    )
    op.create_index(
        op.f("ix_company_invite_tokens_tenant_id"),
        "company_invite_tokens",
        ["tenant_id"],
    )

    op.create_table(
        "pending_app_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_pk", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
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
            name=op.f("fk_pending_app_grants_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["client_pk"],
            ["oauth_clients.id"],
            name=op.f("fk_pending_app_grants_client_pk_oauth_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name=op.f("fk_pending_app_grants_granted_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pending_app_grants")),
        sa.UniqueConstraint(
            "client_pk", "email", name="uq_pending_app_grants_client_email"
        ),
    )
    op.create_index(
        op.f("ix_pending_app_grants_tenant_id"), "pending_app_grants", ["tenant_id"]
    )
    op.create_index(
        op.f("ix_pending_app_grants_client_pk"), "pending_app_grants", ["client_pk"]
    )
    op.create_index(op.f("ix_pending_app_grants_email"), "pending_app_grants", ["email"])

    _enable_rls("pending_app_grants")


def downgrade() -> None:
    _disable_rls("pending_app_grants")
    op.drop_index(op.f("ix_pending_app_grants_email"), table_name="pending_app_grants")
    op.drop_index(op.f("ix_pending_app_grants_client_pk"), table_name="pending_app_grants")
    op.drop_index(op.f("ix_pending_app_grants_tenant_id"), table_name="pending_app_grants")
    op.drop_table("pending_app_grants")
    op.drop_index(
        op.f("ix_company_invite_tokens_tenant_id"), table_name="company_invite_tokens"
    )
    op.drop_table("company_invite_tokens")
