"""Billing: plans, Stripe Checkout (monthly card + Vipps annual), Customer Portal."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.billing import stripe_service
from app.billing.plans import PLANS, PlanId, effective_plan_id, limits_for_tenant
from app.config import settings
from app.db import get_db
from app.models import OAuthClient, Tenant, TenantPlan, User

router = APIRouter(tags=["billing"])


class PlanOut(BaseModel):
    id: str
    max_users: int
    max_apps: int
    audit_retention_days: int
    price_monthly_nok: int | None
    price_annual_nok: int | None


class BillingStatusOut(BaseModel):
    plan: str
    max_users: int
    max_apps: int
    audit_retention_days: int
    users_used: int
    apps_used: int
    plan_expires_at: datetime | None
    stripe_configured: bool
    vipps_enabled: bool
    has_stripe_customer: bool
    can_manage: bool


class CheckoutIn(BaseModel):
    plan: str = Field(pattern="^(team|business)$")
    method: str = Field(pattern="^(card_monthly|vipps_annual)$")


class CheckoutOut(BaseModel):
    url: str


# Display prices (NOK) - Stripe Price IDs are the source of truth for charging.
CATALOG_PRICES = {
    PlanId.free: (None, None),
    PlanId.team: (99, 990),
    PlanId.business: (249, 2490),
}


def _require_owner(user: User) -> None:
    tenant = user.tenant
    if tenant is None or tenant.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_required")


@router.get("/billing/plans", response_model=list[PlanOut])
async def list_plans() -> list[PlanOut]:
    out: list[PlanOut] = []
    for plan_id, limits in PLANS.items():
        monthly, annual = CATALOG_PRICES[plan_id]
        out.append(
            PlanOut(
                id=plan_id.value,
                max_users=limits.max_users,
                max_apps=limits.max_apps,
                audit_retention_days=limits.audit_retention_days,
                price_monthly_nok=monthly,
                price_annual_nok=annual,
            )
        )
    return out


@router.get("/billing/status", response_model=BillingStatusOut)
async def billing_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillingStatusOut:
    tenant = user.tenant
    assert tenant is not None
    # Expire prepaid Vipps annual plans.
    if (
        tenant.plan != TenantPlan.free
        and tenant.plan_expires_at is not None
        and tenant.plan_expires_at < datetime.now(UTC)
        and not tenant.stripe_subscription_id
    ):
        tenant.plan = TenantPlan.free
        tenant.plan_expires_at = None
        await db.commit()

    limits = limits_for_tenant(tenant)
    users_used = await db.scalar(select(func.count()).select_from(User)) or 0
    apps_used = await db.scalar(select(func.count()).select_from(OAuthClient)) or 0
    return BillingStatusOut(
        plan=effective_plan_id(tenant).value,
        max_users=limits.max_users,
        max_apps=limits.max_apps,
        audit_retention_days=limits.audit_retention_days,
        users_used=int(users_used),
        apps_used=int(apps_used),
        plan_expires_at=tenant.plan_expires_at,
        stripe_configured=stripe_service.stripe_configured(),
        vipps_enabled=bool(settings.stripe_vipps_enabled and settings.stripe_price_team_annual),
        has_stripe_customer=bool(tenant.stripe_customer_id),
        can_manage=tenant.owner_user_id == user.id,
    )


@router.post("/billing/checkout", response_model=CheckoutOut)
async def start_checkout(
    body: CheckoutIn,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CheckoutOut:
    _require_owner(user)
    tenant = user.tenant
    assert tenant is not None
    plan = PlanId(body.plan)
    origin = settings.public_origin
    success = f"{origin}/?view=billing&checkout=success"
    cancel = f"{origin}/?view=billing&checkout=cancel"

    if body.method == "card_monthly":
        url = stripe_service.create_subscription_checkout(
            tenant, plan=plan, email=user.email, success_url=success, cancel_url=cancel
        )
    else:
        url = stripe_service.create_vipps_annual_checkout(
            tenant, plan=plan, email=user.email, success_url=success, cancel_url=cancel
        )
    await db.commit()
    return CheckoutOut(url=url)


@router.post("/billing/portal", response_model=CheckoutOut)
async def billing_portal(
    user: User = Depends(require_admin),
) -> CheckoutOut:
    _require_owner(user)
    tenant = user.tenant
    assert tenant is not None
    url = stripe_service.create_billing_portal(
        tenant, return_url=f"{settings.public_origin}/?view=billing"
    )
    return CheckoutOut(url=url)


@router.post("/billing/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    event = stripe_service.parse_webhook(payload, sig)
    etype = event["type"]
    data = event["data"]["object"]

    if etype == "checkout.session.completed":
        meta = data.get("metadata") or {}
        tenant_id = stripe_service.tenant_id_from_metadata(meta)
        plan_raw = meta.get("plan")
        billing = meta.get("billing")
        if tenant_id and plan_raw in {PlanId.team.value, PlanId.business.value}:
            # Webhook has no session tenant RLS - load tenant globally.
            await db.execute(text("SELECT set_config('app.tenant_id', '', true)"))
            tenant = await db.scalar(
                select(Tenant).where(Tenant.id == tenant_id).execution_options(populate_existing=True)
            )
            # Bypass RLS for webhook: tenants table has no RLS.
            if tenant is None:
                tenant = await db.get(Tenant, tenant_id)
            if tenant is not None:
                plan = PlanId(plan_raw)
                if billing == "annual_vipps" or data.get("mode") == "payment":
                    stripe_service.apply_plan(tenant, plan=plan, annual_days=365)
                    if data.get("customer"):
                        tenant.stripe_customer_id = data["customer"]
                else:
                    sub_id = data.get("subscription")
                    stripe_service.apply_plan(
                        tenant, plan=plan, subscription_id=str(sub_id) if sub_id else None
                    )
                    if data.get("customer"):
                        tenant.stripe_customer_id = data["customer"]
                await db.commit()

    elif etype in {"customer.subscription.updated", "customer.subscription.deleted"}:
        sub = data
        meta = sub.get("metadata") or {}
        tenant_id = stripe_service.tenant_id_from_metadata(meta)
        if tenant_id is None and sub.get("id"):
            tenant = await db.scalar(
                select(Tenant).where(Tenant.stripe_subscription_id == sub["id"])
            )
        else:
            tenant = await db.get(Tenant, tenant_id) if tenant_id else None
        if tenant is not None:
            status_value = sub.get("status")
            if etype == "customer.subscription.deleted" or status_value in {
                "canceled",
                "unpaid",
                "incomplete_expired",
            }:
                stripe_service.downgrade_to_free(tenant)
            elif status_value in {"active", "trialing"}:
                plan_raw = meta.get("plan") or (
                    PlanId.team.value if tenant.plan == TenantPlan.team else tenant.plan.value
                )
                if plan_raw in {PlanId.team.value, PlanId.business.value}:
                    stripe_service.apply_plan(
                        tenant, plan=PlanId(plan_raw), subscription_id=sub.get("id")
                    )
            await db.commit()

    return {"received": True}
