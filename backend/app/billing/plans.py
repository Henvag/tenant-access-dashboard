"""Product plans: what free vs paid unlocks (portfolio monetization)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Protocol


class PlanId(str, Enum):
    free = "free"
    team = "team"
    business = "business"


@dataclass(frozen=True)
class PlanLimits:
    id: PlanId
    max_users: int
    max_apps: int
    audit_retention_days: int


PLANS: dict[PlanId, PlanLimits] = {
    PlanId.free: PlanLimits(
        id=PlanId.free, max_users=10, max_apps=3, audit_retention_days=14
    ),
    PlanId.team: PlanLimits(
        id=PlanId.team, max_users=50, max_apps=15, audit_retention_days=90
    ),
    PlanId.business: PlanLimits(
        id=PlanId.business, max_users=250, max_apps=25, audit_retention_days=365
    ),
}


class _TenantPlanLike(Protocol):
    plan: object
    plan_expires_at: datetime | None
    stripe_subscription_id: str | None


def limits_for(plan: str | PlanId) -> PlanLimits:
    try:
        key = PlanId(plan) if not isinstance(plan, PlanId) else plan
    except ValueError:
        key = PlanId.free
    return PLANS[key]


def effective_plan_id(tenant: _TenantPlanLike) -> PlanId:
    """Paid plan, or free if a prepaid Vipps year has expired."""
    raw = getattr(tenant.plan, "value", tenant.plan)
    try:
        plan = PlanId(str(raw))
    except ValueError:
        return PlanId.free
    if plan == PlanId.free:
        return PlanId.free
    if tenant.stripe_subscription_id:
        return plan
    expires = tenant.plan_expires_at
    if expires is not None and expires < datetime.now(UTC):
        return PlanId.free
    return plan


def limits_for_tenant(tenant: _TenantPlanLike) -> PlanLimits:
    return limits_for(effective_plan_id(tenant))


def retention_cutoff(tenant: _TenantPlanLike, *, now: datetime | None = None) -> datetime:
    """Oldest audit timestamp still visible on this plan. Older rows stay stored."""
    moment = now or datetime.now(UTC)
    days = limits_for_tenant(tenant).audit_retention_days
    return moment - timedelta(days=days)
