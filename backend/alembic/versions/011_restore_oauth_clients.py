"""Restore Grafana/Outline oauth_clients by dropping RLS policy briefly.

Revision ID: 011_restore_oauth_clients
Revises: 010_cleanup_outline_pollution
Create Date: 2026-09-20
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "011_restore_oauth_clients"
down_revision: Union[str, None] = "010_cleanup_outline_pollution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GRAFANA_ID = "tad_312f426c58b589e54d59b1de06833c4e"
_OUTLINE_ID = "tad_95a8197dff88bb030fbb3901248c412a"
_TENANT = "40ea72bf-2dc3-4db5-83c4-9b7a50d68759"
_POLICY = "oauth_clients_tenant_isolation"
_PREDICATE = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    import hashlib

    grafana_hash = hashlib.sha256(
        b"8A-O3MA7Cxn5MIlmSnniR-m5mjfKV_3uacIYN_YPKRFfFsWpAwGcng"
    ).hexdigest()
    outline_hash = hashlib.sha256(
        b"evemE-tuRtilWBKkwNGjxBAL7TW_2wadv4IFAZQ9s4-HrnOi9-dCQw"
    ).hexdigest()

    # NO FORCE is not enough when the migration role is not table owner.
    op.execute(text(f"DROP POLICY IF EXISTS {_POLICY} ON oauth_clients"))
    op.execute(text("ALTER TABLE oauth_clients NO FORCE ROW LEVEL SECURITY"))
    op.execute(text("ALTER TABLE oauth_clients DISABLE ROW LEVEL SECURITY"))

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

    op.execute(text("ALTER TABLE oauth_clients ENABLE ROW LEVEL SECURITY"))
    op.execute(text("ALTER TABLE oauth_clients FORCE ROW LEVEL SECURITY"))
    op.execute(
        text(
            f"""
            CREATE POLICY {_POLICY} ON oauth_clients
            USING ({_PREDICATE})
            WITH CHECK ({_PREDICATE})
            """
        )
    )


def downgrade() -> None:
    pass
