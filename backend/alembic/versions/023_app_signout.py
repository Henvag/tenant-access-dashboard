"""Per-app sign-out connector: an admin key Tenant Access uses to end sessions.

Grafana, Outline and Gitea ignore OIDC back-channel logout, so an admin can
store an admin credential for the app instead. On disable we sign the person
out (Grafana) or pause their account (Outline, Gitea) through the app's API.

Revision ID: 023_app_signout
Revises: 022_deletion
Create Date: 2026-11-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023_app_signout"
down_revision: Union[str, None] = "022_deletion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("oauth_clients", sa.Column("signout_kind", sa.String(16), nullable=True))
    op.add_column("oauth_clients", sa.Column("signout_base_url", sa.String(2048), nullable=True))
    op.add_column("oauth_clients", sa.Column("signout_secret", sa.Text(), nullable=True))
    op.add_column("oauth_clients", sa.Column("signout_key_hint", sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column("oauth_clients", "signout_key_hint")
    op.drop_column("oauth_clients", "signout_secret")
    op.drop_column("oauth_clients", "signout_base_url")
    op.drop_column("oauth_clients", "signout_kind")
