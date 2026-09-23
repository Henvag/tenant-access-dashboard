"""Workspace briefing for agents that answer questions about this company.

The briefing is built per request, for the person asking, and only from
rows they could already see in the portal. Members get their own account
and the apps they may open. Admins also get people, every app, and recent
activity. Nothing here is stored; it rides along in the system prompt.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.plans import effective_plan_id, limits_for_tenant, retention_cutoff
from app.models import AccessPolicy, AppGrant, AuditEvent, OAuthClient, TeamAgent, User, UserRole

PEOPLE_LIMIT = 60
EVENTS_LIMIT = 25

PRODUCT_PRIMER = """\
About Tenant Access (the product this workspace runs on):
- People sign in with their Google or Microsoft work account. There are no separate passwords. \
The email domain decides which company workspace they land in.
- Roles: the first person on a domain becomes the owner. The owner can promote members to \
admin and demote them. Admins can see People, Apps, Organization, Audit, and Billing, and can \
disable or enable people. Only the owner can promote, demote, change the logo, or manage billing.
- Disabling a person blocks their next sign-in immediately. Apps that registered a logout URL \
are told to end their session; other apps keep their own session until it expires.
- Apps: company tools that support OpenID Connect (Grafana, Outline, and others) are registered \
under Apps. Tenant Access is their identity provider. Each app has an access policy: everyone, \
admins only, or assigned people. People open their apps from the Overview tab.
- Invite link: admins copy it from People. Anyone with the link signs in with a matching work \
email and joins the workspace.
- Ask: a free Gemini assistant that answers questions about this workspace. An admin pastes one \
Google AI Studio key under Ask. It is not billed like ChatGPT or Claude.
- Agents: company ChatGPT or Claude keys. Messages are billed to that key, not to the person chatting.
- Plans: Free, Team, and Business differ in how many people and apps a workspace can have and \
how long the audit log is kept. Billing is under the Billing tab (owner only).
"""


def _when(value: datetime | None) -> str:
    if value is None:
        return "never"
    return value.strftime("%Y-%m-%d %H:%M UTC")


async def workspace_briefing(db: AsyncSession, user: User) -> str:
    tenant = user.tenant
    plan = effective_plan_id(tenant).value
    limits = limits_for_tenant(tenant)
    is_admin = user.role == UserRole.admin
    is_owner = tenant.owner_user_id is not None and tenant.owner_user_id == user.id

    people_count = await db.scalar(select(func.count()).select_from(User)) or 0
    app_count = await db.scalar(select(func.count()).select_from(OAuthClient)) or 0

    lines: list[str] = [
        PRODUCT_PRIMER,
        "This workspace:",
        f"- Company: {tenant.name} (sign-in domain @{tenant.workspace_domain})",
        f"- Plan: {plan}. Limits: {limits.max_users} people, {limits.max_apps} apps, "
        f"audit log kept {limits.audit_retention_days} days.",
        f"- Usage: {people_count} people, {app_count} apps.",
        "",
        "The person asking:",
        f"- {user.display_name or user.email} ({user.email}), role "
        f"{'owner' if is_owner else user.role.value}, last sign-in {_when(user.last_login_at)}.",
    ]

    lines.append("")
    lines.append("Apps they can open:")
    lines.extend(await _my_apps(db, user))

    if is_admin:
        lines.append("")
        lines.append(f"People (up to {PEOPLE_LIMIT}):")
        lines.extend(await _people(db, tenant.owner_user_id))
        lines.append("")
        lines.append("All apps:")
        lines.extend(await _all_apps(db))
        lines.append("")
        lines.append("Agents in this tab:")
        lines.extend(await _agents(db))
        lines.append("")
        lines.append(f"Recent activity (up to {EVENTS_LIMIT}, within the plan's retention):")
        lines.extend(await _events(db, tenant))

    lines.append("")
    lines.append(
        "Answer from this briefing. If something is not in it, say so and point to the tab "
        "where the person can look. Do not invent people, apps, or events."
    )
    return "\n".join(lines)


async def _my_apps(db: AsyncSession, user: User) -> list[str]:
    granted = set(
        (await db.scalars(select(AppGrant.client_pk).where(AppGrant.user_id == user.id))).all()
    )
    clients = (
        await db.scalars(
            select(OAuthClient).where(OAuthClient.disabled_at.is_(None)).order_by(OAuthClient.name)
        )
    ).all()
    out: list[str] = []
    for client in clients:
        allowed = (
            client.access_policy == AccessPolicy.everyone
            or (client.access_policy == AccessPolicy.admins and user.role == UserRole.admin)
            or (client.access_policy == AccessPolicy.assigned and client.id in granted)
        )
        if allowed:
            launch = f" ({client.launch_url})" if client.launch_url else ""
            out.append(f"- {client.name}{launch}")
    return out or ["- none yet"]


async def _people(db: AsyncSession, owner_id) -> list[str]:
    rows = (
        await db.scalars(select(User).order_by(User.email).limit(PEOPLE_LIMIT))
    ).all()
    out: list[str] = []
    for row in rows:
        role = "owner" if owner_id is not None and row.id == owner_id else row.role.value
        state = "disabled" if row.disabled_at is not None else "active"
        name = row.display_name or row.email
        out.append(f"- {name} <{row.email}>, {role}, {state}, last sign-in {_when(row.last_login_at)}")
    return out or ["- none"]


async def _all_apps(db: AsyncSession) -> list[str]:
    clients = (await db.scalars(select(OAuthClient).order_by(OAuthClient.name))).all()
    out: list[str] = []
    for client in clients:
        state = "disabled" if client.disabled_at is not None else "enabled"
        logout = ", has logout URL" if client.backchannel_logout_uri else ""
        out.append(f"- {client.name}: policy {client.access_policy.value}, {state}{logout}")
    return out or ["- none yet"]


async def _agents(db: AsyncSession) -> list[str]:
    rows = (await db.scalars(select(TeamAgent).order_by(TeamAgent.position))).all()
    return [
        f"- {row.name}: {row.provider} {row.model}, policy {row.access_policy.value}"
        for row in rows
    ] or ["- none"]


async def _events(db: AsyncSession, tenant) -> list[str]:
    cutoff = retention_cutoff(tenant)
    rows = (
        await db.scalars(
            select(AuditEvent)
            .where(AuditEvent.created_at >= cutoff)
            .order_by(AuditEvent.created_at.desc())
            .limit(EVENTS_LIMIT)
        )
    ).all()
    out: list[str] = []
    for row in rows:
        extra = f" ({row.error_code})" if row.error_code else ""
        out.append(f"- {_when(row.created_at)}: {row.event_type.value}{extra}, {row.email}")
    return out or ["- nothing yet"]
