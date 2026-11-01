"""Partner mode: one person can be an outside admin in several companies.

- users: email and (idp, oidc_sub) become unique per company instead of across
  the database, so one sign-in identity can own an account row in each company
  it belongs to. ``external`` marks rows for people from outside the company's
  domains (outside admins). Every request still runs as one row in one company.
- identity_memberships: (idp, oidc_sub) -> (tenant_id, user_id). Read at sign-in
  and when switching company, before the target company is known, so like
  tenant_domains it has no RLS; it holds no names or emails.
- partner_invites: the owner names an exact email address. Sign-in matches
  pending invites by verified email before any tenant is known, so no RLS; the
  API always filters by tenant_id.

Revision ID: 021_partner_mode
Revises: 020_domains_webhooks
Create Date: 2026-11-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "021_partner_mode"
down_revision: Union[str, None] = "020_domains_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_EVENT_TYPES = (
    "partner_invited",
    "partner_invite_revoked",
    "partner_joined",
    "company_switched",
)


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
        "users",
        sa.Column("external", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_constraint("uq_users_idp_oidc_sub", "users", type_="unique")
    op.create_unique_constraint("uq_users_tenant_email", "users", ["tenant_id", "email"])
    op.create_unique_constraint(
        "uq_users_tenant_idp_oidc_sub", "users", ["tenant_id", "idp", "oidc_sub"]
    )

    op.create_table(
        "identity_memberships",
        sa.Column(
            "idp",
            postgresql.ENUM("google", "microsoft", name="identity_provider", create_type=False),
            nullable=False,
        ),
        sa.Column("oidc_sub", sa.String(length=255), nullable=False),
        _uuid("tenant_id", nullable=False),
        _uuid("user_id", nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_identity_memberships_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_identity_memberships_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("idp", "oidc_sub", "tenant_id", name=op.f("pk_identity_memberships")),
    )

    op.create_table(
        "partner_invites",
        _uuid("id", nullable=False),
        _uuid("tenant_id", nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        _uuid("created_by", nullable=True),
        _created_at(),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("accepted_user_id", nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"],
            name=op.f("fk_partner_invites_tenant_id_tenants"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name=op.f("fk_partner_invites_created_by_users"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_user_id"], ["users.id"],
            name=op.f("fk_partner_invites_accepted_user_id_users"), ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_invites")),
        sa.CheckConstraint("email = lower(email)", name="ck_partner_invites_lowercase"),
    )
    op.create_index(op.f("ix_partner_invites_tenant_id"), "partner_invites", ["tenant_id"])
    op.create_index(op.f("ix_partner_invites_email"), "partner_invites", ["email"])
    # One open invite per address per company.
    op.create_index(
        "uq_partner_invites_open",
        "partner_invites",
        ["tenant_id", "email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_partner_invites_open", table_name="partner_invites")
    op.drop_index(op.f("ix_partner_invites_email"), table_name="partner_invites")
    op.drop_index(op.f("ix_partner_invites_tenant_id"), table_name="partner_invites")
    op.drop_table("partner_invites")
    op.drop_table("identity_memberships")
    op.drop_constraint("uq_users_tenant_idp_oidc_sub", "users", type_="unique")
    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
    # Fails if one identity already has rows in several companies; remove those first.
    op.create_unique_constraint("uq_users_idp_oidc_sub", "users", ["idp", "oidc_sub"])
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.drop_column("users", "external")
    # Enum values cannot be removed from audit_event_type; they stay unused.
