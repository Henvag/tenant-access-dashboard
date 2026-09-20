from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TenantPlan(str, enum.Enum):
    free = "free"
    team = "team"
    business = "business"


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint(
            "workspace_domain = lower(workspace_domain)",
            name="domain_lowercase",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    workspace_domain: Mapped[str] = mapped_column(String(253), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_tenants_owner_user_id_users",
        ),
        nullable=True,
        index=True,
    )
    plan: Mapped[TenantPlan] = mapped_column(
        Enum(TenantPlan, name="tenant_plan", create_constraint=False),
        nullable=False,
        default=TenantPlan.free,
        server_default="free",
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    plan_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="tenant",
        foreign_keys="User.tenant_id",
    )
