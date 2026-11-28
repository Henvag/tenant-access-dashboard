"""Built-in Ask: on for every company, with a daily question count.

- tenants.ask_enabled: the owner can turn Ask off. On by default.
- tenants.ask_usage_day / ask_usage_count: questions asked to the built-in
  model today (UTC). Only the number is stored, never the questions.

Revision ID: 026_ask_builtin
Revises: 025_saml
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026_ask_builtin"
down_revision: str | None = "025_saml"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("ask_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column("tenants", sa.Column("ask_usage_day", sa.Date(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("ask_usage_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "ask_usage_count")
    op.drop_column("tenants", "ask_usage_day")
    op.drop_column("tenants", "ask_enabled")
