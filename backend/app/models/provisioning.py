from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppAccount(Base):
    """A person's account in an app that Tenant Access creates and deactivates.

    One row per app and email address. ``user_id`` is empty while the person
    only has a pending (email) grant, and after they are deleted.
    """

    __tablename__ = "app_accounts"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    client_pk: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("oauth_clients.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Emptied when the person is deleted; the remote id is enough to deactivate.
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    # The account's id in the app (Slack: U0123ABC).
    remote_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # pending -> active | deactivated | none | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    last_error: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProvisionOutbox(Base):
    """Secret-free queue row, like webhook_outbox: due work without tenant context."""

    __tablename__ = "provision_outbox"

    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app_accounts.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
