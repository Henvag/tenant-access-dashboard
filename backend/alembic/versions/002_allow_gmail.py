"""Allow personal Gmail domains for local/demo sign-in.

Revision ID: 002_allow_gmail
Revises: 001_initial
Create Date: 2026-03-18
"""

from typing import Sequence, Union

from alembic import op

revision: str = "002_allow_gmail"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_tenants_no_consumer_gmail", "tenants", type_="check")


def downgrade() -> None:
    op.create_check_constraint(
        "ck_tenants_no_consumer_gmail",
        "tenants",
        "workspace_domain NOT IN ('gmail.com', 'googlemail.com')",
    )
