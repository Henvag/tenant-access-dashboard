"""Support Google and Microsoft IdP subjects on users.

Revision ID: 003_idp_subjects
Revises: 002_allow_gmail
Create Date: 2026-03-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_idp_subjects"
down_revision: Union[str, None] = "002_allow_gmail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

idp_enum = sa.Enum("google", "microsoft", name="identity_provider")


def upgrade() -> None:
    idp_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("idp", idp_enum, nullable=False, server_default="google"),
    )
    op.alter_column("users", "idp", server_default=None)
    op.alter_column("users", "google_sub", new_column_name="oidc_sub")
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.create_unique_constraint("uq_users_idp_oidc_sub", "users", ["idp", "oidc_sub"])


def downgrade() -> None:
    op.drop_constraint("uq_users_idp_oidc_sub", "users", type_="unique")
    op.create_unique_constraint("uq_users_google_sub", "users", ["oidc_sub"])
    op.alter_column("users", "oidc_sub", new_column_name="google_sub")
    op.drop_column("users", "idp")
    idp_enum.drop(op.get_bind(), checkfirst=True)
