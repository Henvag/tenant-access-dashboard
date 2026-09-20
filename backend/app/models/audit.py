from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.user import IdentityProvider


class AuditEventType(str, enum.Enum):
    login = "login"
    login_failed = "login_failed"
    user_disabled = "user_disabled"
    user_enabled = "user_enabled"
    role_changed = "role_changed"
    app_created = "app_created"
    app_deleted = "app_deleted"
    app_access_granted = "app_access_granted"
    app_access_revoked = "app_access_revoked"
    app_login = "app_login"
    app_login_denied = "app_login_denied"


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    event_type: Mapped[AuditEventType] = mapped_column(
        Enum(AuditEventType, name="audit_event_type", create_constraint=False),
        nullable=False,
    )
    idp: Mapped[IdentityProvider] = mapped_column(
        Enum(IdentityProvider, name="identity_provider", create_constraint=False),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Free-form context (app name, denial reason, from/to role). Nullable for old rows.
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship()
    user: Mapped["User | None"] = relationship()
