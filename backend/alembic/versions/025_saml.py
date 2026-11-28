"""SAML sign-in: apps that sign people in with SAML 2.0 (Slack, Zoom and other cloud apps).

- oauth_clients.protocol: "oidc" (default, every existing app) or "saml".
- oauth_clients.saml_*: the app's entity ID (audience), where we post the
  signed response (ACS URL), and which NameID it wants.
- saml_certificates: our signing key and self-signed certificate. Global, like
  signing_keys: admins paste the certificate into the app once, so it does not
  rotate with the OpenID Connect keys.

Revision ID: 025_saml
Revises: 024_provisioning
Create Date: 2026-11-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "025_saml"
down_revision: Union[str, None] = "024_provisioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "oauth_clients",
        sa.Column("protocol", sa.String(8), nullable=False, server_default="oidc"),
    )
    op.add_column("oauth_clients", sa.Column("saml_entity_id", sa.String(2048), nullable=True))
    op.add_column("oauth_clients", sa.Column("saml_acs_url", sa.String(2048), nullable=True))
    op.add_column("oauth_clients", sa.Column("saml_nameid", sa.String(16), nullable=True))
    op.create_table(
        "saml_certificates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("private_pem", sa.Text(), nullable=False),
        sa.Column("certificate_pem", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("saml_certificates")
    op.drop_column("oauth_clients", "saml_nameid")
    op.drop_column("oauth_clients", "saml_acs_url")
    op.drop_column("oauth_clients", "saml_entity_id")
    op.drop_column("oauth_clients", "protocol")
