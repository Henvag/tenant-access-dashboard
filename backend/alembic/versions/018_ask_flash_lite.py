"""Prefer Gemini Flash-Lite for free Ask quota (about 500 requests/day).

Revision ID: 018_ask_flash_lite
Revises: 017_workspace_ask
Create Date: 2026-09-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "018_ask_flash_lite"
down_revision: Union[str, None] = "017_workspace_ask"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Full Flash free tier is typically only about 20 RPD. Flash-Lite is about 500.
    op.execute(
        """
        UPDATE tenants
        SET ask_model = 'gemini-3.5-flash-lite'
        WHERE ask_secret IS NOT NULL
          AND (ask_model IS NULL OR ask_model = 'gemini-3.8-flash')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE tenants
        SET ask_model = 'gemini-3.8-flash'
        WHERE ask_model = 'gemini-3.5-flash-lite'
        """
    )
