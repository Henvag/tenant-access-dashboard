from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class IdentityProvider(str, enum.Enum):
    google = "google"
    microsoft = "microsoft"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email"),
        UniqueConstraint("idp", "oidc_sub"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    idp: Mapped[IdentityProvider] = mapped_column(
        Enum(IdentityProvider, name="identity_provider"),
        nullable=False,
    )
    oidc_sub: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship(
        back_populates="users",
        foreign_keys=[tenant_id],
    )

    @property
    def disabled(self) -> bool:
        return self.disabled_at is not None
