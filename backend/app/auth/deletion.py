"""Deleting a person or a whole company.

A person: their account row goes, together with what only exists for them (app
grants, sign-in codes, their company membership). Audit events about them stay,
so the company can still see what happened, but their email, IP address and
browser are removed from those rows and from the webhook delivery log.

A company: the tenant row goes and every table that refers to it cascades.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, or_, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, PartnerInvite, PendingAppGrant, Tenant, User

# An emptied address. The dashboard shows it as "Deleted person".
DELETED_EMAIL = ""

# Audit details that can hold another person's address.
_DETAIL_EMAIL_KEYS = ("by", "email")


async def forget_person(session: AsyncSession, user: User) -> None:
    """Delete ``user`` and remove their address from the company's records.

    RLS must already be set for the user's company. Every statement also filters
    on tenant_id, so an outside admin keeps their rows in other companies.
    """
    tenant_id = user.tenant_id
    email = user.email
    params = {"tenant_id": tenant_id, "email": email}

    await session.execute(
        update(AuditEvent)
        .where(
            AuditEvent.tenant_id == tenant_id,
            or_(AuditEvent.user_id == user.id, AuditEvent.email == email),
        )
        .values(email=DELETED_EMAIL, ip_address=None, user_agent=None)
    )
    for key in _DETAIL_EMAIL_KEYS:
        await session.execute(
            text(
                "UPDATE audit_events SET details = jsonb_set(details, CAST(:path AS text[]), '\"\"') "
                "WHERE tenant_id = :tenant_id AND details ->> :key = :email"
            ),
            {**params, "key": key, "path": [key]},
        )

    # Webhook payloads are copies of audit rows, kept for 30 days.
    await session.execute(
        text(
            "UPDATE webhook_deliveries "
            "SET payload = jsonb_set(payload #- '{data,ip_address}', '{data,email}', '\"\"') "
            "WHERE tenant_id = :tenant_id AND payload #>> '{data,email}' = :email"
        ),
        params,
    )
    for key in _DETAIL_EMAIL_KEYS:
        await session.execute(
            text(
                "UPDATE webhook_deliveries "
                "SET payload = jsonb_set(payload, CAST(:path AS text[]), '\"\"') "
                "WHERE tenant_id = :tenant_id AND payload #>> CAST(:path AS text[]) = :email"
            ),
            {**params, "path": ["data", "details", key]},
        )

    await session.execute(
        delete(PendingAppGrant).where(
            PendingAppGrant.tenant_id == tenant_id, PendingAppGrant.email == email
        )
    )
    await session.execute(
        delete(PartnerInvite).where(
            PartnerInvite.tenant_id == tenant_id, PartnerInvite.email == email
        )
    )
    # A plain DELETE so the database's own cascades run (grants, codes, memberships).
    await session.execute(delete(User).where(User.id == user.id, User.tenant_id == tenant_id))
    session.expunge(user)


async def delete_company(session: AsyncSession, tenant_id: UUID) -> None:
    """Delete the company and, by cascade, everything stored for it."""
    await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
