"""Add tenants.owner_user_id for company founder (superadmin).

Revision ID: 007_tenant_owner
Revises: 006_user_disabled
Create Date: 2026-03-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_tenant_owner"
down_revision: Union[str, None] = "006_user_disabled"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Earliest admin per tenant (by id) becomes owner for existing data.
    op.execute(
        """
        UPDATE tenants t
        SET owner_user_id = u.id
        FROM (
            SELECT DISTINCT ON (tenant_id) id, tenant_id
            FROM users
            WHERE role = 'admin'
            ORDER BY tenant_id, id
        ) u
        WHERE t.id = u.tenant_id
          AND t.owner_user_id IS NULL
        """
    )
    # Tenants with no admin: fall back to earliest user.
    op.execute(
        """
        UPDATE tenants t
        SET owner_user_id = u.id
        FROM (
            SELECT DISTINCT ON (tenant_id) id, tenant_id
            FROM users
            ORDER BY tenant_id, id
        ) u
        WHERE t.id = u.tenant_id
          AND t.owner_user_id IS NULL
        """
    )
    op.create_foreign_key(
        op.f("fk_tenants_owner_user_id_users"),
        "tenants",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_tenants_owner_user_id"), "tenants", ["owner_user_id"])

    op.execute(
        """
        DO $$ BEGIN
            ALTER TYPE audit_event_type ADD VALUE 'role_changed';
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tenants_owner_user_id"), table_name="tenants")
    op.drop_constraint(op.f("fk_tenants_owner_user_id_users"), "tenants", type_="foreignkey")
    op.drop_column("tenants", "owner_user_id")
    # Postgres cannot remove enum values safely.
