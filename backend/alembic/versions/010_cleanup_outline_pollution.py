"""Create dedicated Outline DB, clean pollution, restore OAuth clients.

Revision ID: 010_cleanup_outline_pollution
Revises: 009_oauth_provider
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "010_cleanup_outline_pollution"
down_revision: Union[str, None] = "009_oauth_provider"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GRAFANA_ID = "tad_312f426c58b589e54d59b1de06833c4e"
_OUTLINE_ID = "tad_95a8197dff88bb030fbb3901248c412a"
_TENANT = "40ea72bf-2dc3-4db5-83c4-9b7a50d68759"


def upgrade() -> None:
    import hashlib

    grafana_hash = hashlib.sha256(
        b"8A-O3MA7Cxn5MIlmSnniR-m5mjfKV_3uacIYN_YPKRFfFsWpAwGcng"
    ).hexdigest()
    outline_hash = hashlib.sha256(
        b"evemE-tuRtilWBKkwNGjxBAL7TW_2wadv4IFAZQ9s4-HrnOi9-dCQw"
    ).hexdigest()

    # Outline briefly ran migrations against tenant_access_db.
    op.execute(text('DROP TABLE IF EXISTS documents CASCADE'))
    op.execute(text('DROP TABLE IF EXISTS atlases CASCADE'))
    op.execute(text('DROP TABLE IF EXISTS teams CASCADE'))
    op.execute(text('DROP TABLE IF EXISTS "SequelizeMeta" CASCADE'))

    op.execute(text(f"UPDATE tenants SET owner_user_id = NULL WHERE id = '{_TENANT}'"))

    op.execute(
        text(
            f"""
            INSERT INTO oauth_clients (
                id, tenant_id, name, client_id, client_secret_hash,
                redirect_uris, launch_url, access_policy, created_by
            )
            SELECT gen_random_uuid(), '{_TENANT}', 'Grafana', '{_GRAFANA_ID}', '{grafana_hash}',
                   ARRAY['https://tenant-access-grafana.onrender.com/login/generic_oauth'],
                   'https://tenant-access-grafana.onrender.com',
                   'everyone'::oauth_access_policy, NULL
            WHERE NOT EXISTS (SELECT 1 FROM oauth_clients WHERE client_id = '{_GRAFANA_ID}')
            """
        )
    )
    op.execute(
        text(
            f"""
            INSERT INTO oauth_clients (
                id, tenant_id, name, client_id, client_secret_hash,
                redirect_uris, launch_url, access_policy, created_by
            )
            SELECT gen_random_uuid(), '{_TENANT}', 'Outline', '{_OUTLINE_ID}', '{outline_hash}',
                   ARRAY['https://tenant-access-outline.onrender.com/auth/oidc.callback'],
                   'https://tenant-access-outline.onrender.com',
                   'everyone'::oauth_access_policy, NULL
            WHERE NOT EXISTS (SELECT 1 FROM oauth_clients WHERE client_id = '{_OUTLINE_ID}')
            """
        )
    )

    # Separate database for Outline (same instance; free tier = one Postgres).
    with op.get_context().autocommit_block():
        exists = op.get_bind().execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'outline'")
        ).scalar()
        if not exists:
            op.execute(text("CREATE DATABASE outline"))


def downgrade() -> None:
    pass
