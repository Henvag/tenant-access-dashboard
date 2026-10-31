"""Public read-only demo company.

Visitors can explore the dashboard without Google or Microsoft: ``POST /auth/demo``
signs them in as the owner of a fixed sample company. Every write is refused for
that session (see ``enforce_demo_read_only``), its apps are not connected to any
real relying party, it has no Ask or agent keys, and the data is seeded or
refreshed on each demo sign-in so it always looks recent. The demo refuses to
start when the database role bypasses row-level security.

The company uses the reserved ``.example`` TLD, so no real Google or Microsoft
account can ever resolve to it, and its users have subjects no IdP issues.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.rls import set_tenant_rls
from app.models import (
    AccessPolicy,
    AppGrant,
    AuditEvent,
    AuditEventType,
    IdentityProvider,
    OAuthClient,
    OAuthClientLookup,
    Tenant,
    TenantPlan,
    User,
    UserRole,
)
from app.oauth.service import hash_secret, new_client_id

DEMO_TENANT_ID = UUID("6d656d6f-0000-4000-8000-000000000001")
DEMO_DOMAIN = "nordlys.example"
DEMO_NAME = "Nordlys Analytics"
DEMO_SESSION_KEY = "demo"
# Marks rows written by the seeder, so refreshes can move them and prune the rest.
SEED_MARKER = "tenant-access-demo-seed"
# Visitor-generated audit rows (app sign-ins) older than this are pruned.
VISITOR_EVENT_TTL = timedelta(hours=24)
# Shift seeded timestamps once the newest one is older than this.
REFRESH_AFTER = timedelta(hours=1)
_ADVISORY_LOCK = 7_340_221

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Writes a demo session may still make: starting the demo again.
_DEMO_WRITE_ALLOWED = frozenset({"/auth/demo"})


@dataclass(frozen=True)
class _Person:
    key: str
    name: str
    role: UserRole
    idp: IdentityProvider
    last_login_hours: float | None
    disabled: bool = False

    @property
    def email(self) -> str:
        return f"{self.key}@{DEMO_DOMAIN}"


PEOPLE: tuple[_Person, ...] = (
    _Person("ingrid.berg", "Ingrid Berg", UserRole.admin, IdentityProvider.google, 0.3),
    _Person("lars.haugen", "Lars Haugen", UserRole.admin, IdentityProvider.microsoft, 2),
    _Person("sofie.nilsen", "Sofie Nilsen", UserRole.user, IdentityProvider.google, 5),
    _Person("emil.dahl", "Emil Dahl", UserRole.user, IdentityProvider.microsoft, 20),
    _Person("maja.johansen", "Maja Johansen", UserRole.user, IdentityProvider.google, 30),
    _Person("aksel.strand", "Aksel Strand", UserRole.user, IdentityProvider.google, 70),
    _Person("nora.bakken", "Nora Bakken", UserRole.user, IdentityProvider.microsoft, 130),
    _Person("thea.moen", "Thea Moen", UserRole.user, IdentityProvider.microsoft, None),
    _Person(
        "jonas.lie", "Jonas Lie", UserRole.user, IdentityProvider.google, 200, disabled=True
    ),
)
OWNER_KEY = "ingrid.berg"


@dataclass(frozen=True)
class _App:
    name: str
    redirect_uri: str
    launch_url: str | None
    policy: AccessPolicy
    assigned: tuple[str, ...] = ()


# Self-contained: redirect URIs live on the reserved demo domain and nothing is
# launchable, so a demo session never reaches a real relying party.
APPS: tuple[_App, ...] = (
    _App(
        "Grafana",
        f"https://grafana.{DEMO_DOMAIN}/login/generic_oauth",
        None,
        AccessPolicy.everyone,
    ),
    _App(
        "Outline",
        f"https://wiki.{DEMO_DOMAIN}/auth/oidc.callback",
        None,
        AccessPolicy.assigned,
        assigned=("ingrid.berg", "lars.haugen", "sofie.nilsen", "maja.johansen"),
    ),
    _App(
        "Gitea",
        f"https://git.{DEMO_DOMAIN}/user/oauth2/tenant-access/callback",
        None,
        AccessPolicy.admins,
    ),
)


# (hours ago, event type, person key, ip suffix, error_code, details)
_EVENTS: tuple[tuple[float, AuditEventType, str, int, str | None, dict | None], ...] = (
    (236, AuditEventType.app_created, "ingrid.berg", 10, None, {"app": "Grafana", "policy": "everyone"}),
    (235, AuditEventType.app_created, "ingrid.berg", 10, None, {"app": "Outline", "policy": "assigned"}),
    (234, AuditEventType.app_access_granted, "lars.haugen", 10, None, {"app": "Outline", "by": "ingrid.berg"}),
    (234, AuditEventType.app_access_granted, "sofie.nilsen", 10, None, {"app": "Outline", "by": "ingrid.berg"}),
    (233, AuditEventType.app_access_granted, "maja.johansen", 10, None, {"app": "Outline", "by": "ingrid.berg"}),
    (220, AuditEventType.role_changed, "lars.haugen", 10, "user->admin", {"from_role": "user", "to_role": "admin"}),
    (200, AuditEventType.login, "jonas.lie", 44, None, None),
    (190, AuditEventType.user_disabled, "jonas.lie", 10, None, None),
    (160, AuditEventType.app_created, "lars.haugen", 21, None, {"app": "Gitea", "policy": "admins"}),
    (131, AuditEventType.login_failed, "jonas.lie", 44, "user_disabled", None),
    (130, AuditEventType.login, "nora.bakken", 63, None, None),
    (129, AuditEventType.app_login, "nora.bakken", 63, None, {"app": "Grafana"}),
    (71, AuditEventType.login, "aksel.strand", 87, None, None),
    (70, AuditEventType.app_login, "aksel.strand", 87, None, {"app": "Grafana"}),
    (31, AuditEventType.login, "maja.johansen", 52, None, None),
    (30, AuditEventType.app_login, "maja.johansen", 52, None, {"app": "Outline"}),
    (29, AuditEventType.app_login_denied, "maja.johansen", 52, "admins_only", {"app": "Gitea", "reason": "admins_only"}),
    (21, AuditEventType.login, "emil.dahl", 33, None, None),
    (20, AuditEventType.app_login_denied, "emil.dahl", 33, "not_assigned", {"app": "Outline", "reason": "not_assigned"}),
    (19.5, AuditEventType.app_login, "emil.dahl", 33, None, {"app": "Grafana"}),
    (6, AuditEventType.login_failed, "contractor", 140, "unverified_email", None),
    (5, AuditEventType.login, "sofie.nilsen", 18, None, None),
    (4.8, AuditEventType.app_login, "sofie.nilsen", 18, None, {"app": "Outline"}),
    (2, AuditEventType.login, "lars.haugen", 21, None, None),
    (1.9, AuditEventType.app_login, "lars.haugen", 21, None, {"app": "Gitea"}),
    (0.3, AuditEventType.login, "ingrid.berg", 10, None, None),
)


def is_demo_tenant(tenant_id: UUID | str | None) -> bool:
    return tenant_id is not None and str(tenant_id) == str(DEMO_TENANT_ID)


def is_demo_session(session_data: dict) -> bool:
    return bool(session_data.get(DEMO_SESSION_KEY))


async def enforce_demo_read_only(request: Request) -> None:
    """App-wide dependency: a demo session may look, never change anything."""
    if request.method in SAFE_METHODS or request.url.path in _DEMO_WRITE_ALLOWED:
        return
    if "session" not in request.scope:
        return
    if is_demo_session(request.session):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="demo_read_only")


async def database_enforces_rls(db: AsyncSession) -> bool:
    """False when the connected role is a superuser or has BYPASSRLS.

    The demo puts anonymous visitors in an admin seat. Admin queries rely on
    Postgres RLS for tenant isolation, so without it they would see every company.
    """
    bypasses = await db.scalar(
        text(
            "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
    )
    return bypasses is False


def _ip(suffix: int) -> str:
    # RFC 5737 documentation range: never a real visitor address.
    return f"203.0.113.{suffix}"


async def _seed(db: AsyncSession, now: datetime) -> None:
    tenant = Tenant(
        id=DEMO_TENANT_ID,
        name=DEMO_NAME,
        workspace_domain=DEMO_DOMAIN,
        plan=TenantPlan.team,
    )
    db.add(tenant)
    await db.flush()
    await set_tenant_rls(db, DEMO_TENANT_ID)

    users: dict[str, User] = {}
    for person in PEOPLE:
        user = User(
            tenant_id=DEMO_TENANT_ID,
            email=person.email,
            idp=person.idp,
            oidc_sub=f"demo:{person.key}",
            role=person.role,
            display_name=person.name,
            last_login_at=(
                now - timedelta(hours=person.last_login_hours)
                if person.last_login_hours is not None
                else None
            ),
            disabled_at=now - timedelta(hours=190) if person.disabled else None,
        )
        db.add(user)
        users[person.key] = user
    await db.flush()
    owner = users[OWNER_KEY]
    tenant.owner_user_id = owner.id

    for spec in APPS:
        client_id = new_client_id()
        # The secret is thrown away: no relying party can ever finish a sign-in.
        client = OAuthClient(
            tenant_id=DEMO_TENANT_ID,
            name=spec.name,
            client_id=client_id,
            client_secret_hash=hash_secret(secrets.token_urlsafe(32)),
            redirect_uris=[spec.redirect_uri],
            launch_url=spec.launch_url,
            access_policy=spec.policy,
            created_by=owner.id,
            created_at=now - timedelta(hours=236),
        )
        db.add(client)
        db.add(OAuthClientLookup(client_id=client_id, tenant_id=DEMO_TENANT_ID))
        await db.flush()
        for key in spec.assigned:
            db.add(
                AppGrant(
                    tenant_id=DEMO_TENANT_ID,
                    client_pk=client.id,
                    user_id=users[key].id,
                    granted_by=owner.id,
                )
            )

    by_email = {p.email: p for p in PEOPLE}
    for hours, event_type, key, ip_suffix, error_code, details in _EVENTS:
        email = f"{key}@{DEMO_DOMAIN}"
        person = by_email.get(email)
        user = users.get(key)
        if details and details.get("by"):
            details = {**details, "by": f"{details['by']}@{DEMO_DOMAIN}"}
        db.add(
            AuditEvent(
                tenant_id=DEMO_TENANT_ID,
                user_id=user.id if user else None,
                email=email,
                event_type=event_type,
                idp=person.idp if person else IdentityProvider.google,
                error_code=error_code,
                ip_address=_ip(ip_suffix),
                user_agent=SEED_MARKER,
                details=details,
                created_at=now - timedelta(hours=hours),
            )
        )
    await db.flush()


async def _refresh(db: AsyncSession, now: datetime) -> None:
    """Keep seeded activity recent and drop old visitor rows."""
    await set_tenant_rls(db, DEMO_TENANT_ID)
    newest = await db.scalar(
        select(func.max(AuditEvent.created_at)).where(AuditEvent.user_agent == SEED_MARKER)
    )
    if newest is not None:
        # The newest seeded row is the owner's sign-in, 0.3 h before seeding.
        shift = now - timedelta(hours=0.3) - newest
        if shift > REFRESH_AFTER:
            await db.execute(
                update(AuditEvent)
                .where(AuditEvent.user_agent == SEED_MARKER)
                .values(created_at=AuditEvent.created_at + shift)
            )
            await db.execute(
                update(User)
                .where(User.last_login_at.is_not(None))
                .values(last_login_at=User.last_login_at + shift)
            )
            await db.execute(
                update(User)
                .where(User.disabled_at.is_not(None))
                .values(disabled_at=User.disabled_at + shift)
            )
    await db.execute(
        delete(AuditEvent).where(
            (AuditEvent.user_agent.is_(None)) | (AuditEvent.user_agent != SEED_MARKER),
            AuditEvent.created_at < now - VISITOR_EVENT_TTL,
        )
    )


async def ensure_demo_owner(db: AsyncSession) -> User:
    """Create the demo company on first use, refresh it, and return its owner.

    Serialised with an advisory lock so concurrent first visits cannot race.
    Leaves RLS scoped to the demo tenant; the caller commits.
    """
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK})
    now = datetime.now(UTC)
    exists = await db.scalar(select(Tenant.id).where(Tenant.id == DEMO_TENANT_ID))
    if exists is None:
        await _seed(db, now)
    else:
        await _refresh(db, now)
    await set_tenant_rls(db, DEMO_TENANT_ID)
    owner = await db.scalar(
        select(User).where(User.email == f"{OWNER_KEY}@{DEMO_DOMAIN}")
    )
    if owner is None:  # pragma: no cover - only if someone deleted the owner row
        raise RuntimeError("demo owner missing")
    return owner
