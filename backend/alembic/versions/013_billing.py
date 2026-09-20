"""Tenant plans and Stripe billing fields.

Revision ID: 013_billing
Revises: 012_invites
Create Date: 2026-09-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013_billing"
down_revision: Union[str, None] = "012_invites"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE tenant_plan AS ENUM ('free', 'team', 'business');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    plan = postgresql.ENUM(
        "free", "team", "business", name="tenant_plan", create_type=False
    )
    op.add_column(
        "tenants",
        sa.Column("plan", plan, server_default="free", nullable=False),
    )
    op.add_column(
        "tenants",
        sa.Column("stripe_customer_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("stripe_subscription_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_tenants_stripe_customer_id"), "tenants", ["stripe_customer_id"], unique=False
    )
    op.create_index(
        op.f("ix_tenants_stripe_subscription_id"),
        "tenants",
        ["stripe_subscription_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tenants_stripe_subscription_id"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_stripe_customer_id"), table_name="tenants")
    op.drop_column("tenants", "plan_expires_at")
    op.drop_column("tenants", "stripe_subscription_id")
    op.drop_column("tenants", "stripe_customer_id")
    op.drop_column("tenants", "plan")
    op.execute("DROP TYPE IF EXISTS tenant_plan")
