"""Stripe Checkout (card subscriptions + Vipps annual one-shot)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import stripe
from fastapi import HTTPException, status

from app.billing.plans import PlanId
from app.config import settings
from app.models import Tenant, TenantPlan


def stripe_configured() -> bool:
    return bool(settings.stripe_secret_key)


def _configure() -> None:
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="stripe_unconfigured"
        )
    stripe.api_key = settings.stripe_secret_key


def _price_for(plan: PlanId, *, annual: bool) -> str:
    mapping = {
        (PlanId.team, False): settings.stripe_price_team_monthly,
        (PlanId.business, False): settings.stripe_price_business_monthly,
        (PlanId.team, True): settings.stripe_price_team_annual,
        (PlanId.business, True): settings.stripe_price_business_annual,
    }
    price = mapping.get((plan, annual), "")
    if not price:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="stripe_price_unconfigured",
        )
    return price


def ensure_customer(tenant: Tenant, *, email: str) -> str:
    _configure()
    if tenant.stripe_customer_id:
        return tenant.stripe_customer_id
    customer = stripe.Customer.create(
        email=email,
        name=tenant.name,
        metadata={"tenant_id": str(tenant.id), "domain": tenant.workspace_domain},
    )
    tenant.stripe_customer_id = customer.id
    return customer.id


def create_subscription_checkout(
    tenant: Tenant,
    *,
    plan: PlanId,
    email: str,
    success_url: str,
    cancel_url: str,
) -> str:
    if plan == PlanId.free:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_plan")
    _configure()
    customer_id = ensure_customer(tenant, email=email)
    price = _price_for(plan, annual=False)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[{"price": price, "quantity": 1}],
        allow_promotion_codes=True,
        metadata={
            "tenant_id": str(tenant.id),
            "plan": plan.value,
            "billing": "monthly",
        },
        subscription_data={
            "metadata": {"tenant_id": str(tenant.id), "plan": plan.value},
        },
    )
    if not session.url:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="stripe_session_failed")
    return session.url


def create_vipps_annual_checkout(
    tenant: Tenant,
    *,
    plan: PlanId,
    email: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """One-year prepaid via Vipps (Stripe payment mode).

    Stripe Vipps cannot run in subscription Checkout mode, so annual is a
    one-time payment that sets plan_expires_at for 365 days.
    """
    if plan == PlanId.free:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_plan")
    if not settings.stripe_vipps_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="vipps_unconfigured"
        )
    _configure()
    customer_id = ensure_customer(tenant, email=email)
    price = _price_for(plan, annual=True)
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=customer_id,
        success_url=success_url,
        cancel_url=cancel_url,
        line_items=[{"price": price, "quantity": 1}],
        payment_method_types=["vipps", "card"],
        metadata={
            "tenant_id": str(tenant.id),
            "plan": plan.value,
            "billing": "annual_vipps",
        },
    )
    if not session.url:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="stripe_session_failed")
    return session.url


def create_billing_portal(tenant: Tenant, *, return_url: str) -> str:
    _configure()
    if not tenant.stripe_customer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no_stripe_customer")
    session = stripe.billing_portal.Session.create(
        customer=tenant.stripe_customer_id,
        return_url=return_url,
    )
    if not session.url:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="stripe_session_failed")
    return session.url


def apply_plan(
    tenant: Tenant,
    *,
    plan: PlanId,
    subscription_id: str | None = None,
    annual_days: int | None = None,
) -> None:
    tenant.plan = TenantPlan(plan.value)
    if subscription_id is not None:
        tenant.stripe_subscription_id = subscription_id
        tenant.plan_expires_at = None
    if annual_days is not None:
        tenant.stripe_subscription_id = None
        tenant.plan_expires_at = datetime.now(UTC) + timedelta(days=annual_days)


def downgrade_to_free(tenant: Tenant) -> None:
    tenant.plan = TenantPlan.free
    tenant.stripe_subscription_id = None
    tenant.plan_expires_at = None


def parse_webhook(payload: bytes, sig_header: str) -> dict[str, Any]:
    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="stripe_unconfigured"
        )
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_stripe_signature"
        ) from exc
    # stripe-python returns StripeObjects; convert so handlers can use .get().
    if hasattr(event, "to_dict"):
        return event.to_dict()
    return dict(event)


def tenant_id_from_metadata(meta: dict | Any | None) -> UUID | None:
    if not meta:
        return None
    if hasattr(meta, "to_dict"):
        meta = meta.to_dict()
    raw = meta.get("tenant_id") if isinstance(meta, dict) else getattr(meta, "tenant_id", None)
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None
