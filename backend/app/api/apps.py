"""Admin management of registered apps (OIDC clients) and per-user grants."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.auth.audit import record_app_event
from app.db import get_db
from app.billing.plans import limits_for_tenant
from app.domain import normalize_workspace_domain
from app.models import (
    AccessPolicy,
    AppGrant,
    AuditEventType,
    OAuthClient,
    OAuthClientLookup,
    PendingAppGrant,
    User,
    UserRole,
)
from app.oauth.service import hash_secret, new_client_id, new_client_secret
from app.schemas.app import (
    AppCreate,
    AppCreatedOut,
    AppOut,
    AppPatch,
    GrantsIn,
    GrantsOut,
    MyAppOut,
    SecretOut,
)

router = APIRouter(prefix="/apps", tags=["apps"])


async def _grant_counts(db: AsyncSession, client_pks: list[UUID]) -> dict[UUID, int]:
    if not client_pks:
        return {}
    rows = await db.execute(
        select(AppGrant.client_pk, func.count())
        .where(AppGrant.client_pk.in_(client_pks))
        .group_by(AppGrant.client_pk)
    )
    counts = {pk: count for pk, count in rows.all()}
    pending_rows = await db.execute(
        select(PendingAppGrant.client_pk, func.count())
        .where(PendingAppGrant.client_pk.in_(client_pks))
        .group_by(PendingAppGrant.client_pk)
    )
    for pk, count in pending_rows.all():
        counts[pk] = counts.get(pk, 0) + count
    return counts


def _to_out(client: OAuthClient, grant_count: int) -> AppOut:
    return AppOut(
        id=client.id,
        name=client.name,
        client_id=client.client_id,
        redirect_uris=list(client.redirect_uris),
        launch_url=client.launch_url,
        access_policy=client.access_policy,
        disabled=client.disabled,
        created_at=client.created_at,
        grant_count=grant_count,
    )


async def _load(db: AsyncSession, app_id: UUID) -> OAuthClient:
    client = await db.scalar(select(OAuthClient).where(OAuthClient.id == app_id))
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="app_not_found")
    return client


# ---------- everyone ----------


@router.get("/mine", response_model=list[MyAppOut])
async def my_apps(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[MyAppOut]:
    """Apps this user may launch: not disabled, and allowed by the access policy."""
    granted_pks = set(
        (await db.scalars(select(AppGrant.client_pk).where(AppGrant.user_id == user.id))).all()
    )
    clients = (
        await db.scalars(
            select(OAuthClient)
            .where(OAuthClient.disabled_at.is_(None))
            .order_by(OAuthClient.name)
        )
    ).all()
    visible: list[MyAppOut] = []
    for client in clients:
        allowed = (
            client.access_policy == AccessPolicy.everyone
            or (client.access_policy == AccessPolicy.admins and user.role == UserRole.admin)
            or (client.access_policy == AccessPolicy.assigned and client.id in granted_pks)
        )
        if allowed:
            visible.append(
                MyAppOut(
                    id=client.id,
                    name=client.name,
                    launch_url=client.launch_url,
                    access_policy=client.access_policy,
                )
            )
    return visible


# ---------- admin ----------


@router.get("", response_model=list[AppOut])
async def list_apps(
    _admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[AppOut]:
    clients = list(
        (await db.scalars(select(OAuthClient).order_by(OAuthClient.created_at))).all()
    )
    counts = await _grant_counts(db, [c.id for c in clients])
    return [_to_out(c, counts.get(c.id, 0)) for c in clients]


@router.post("", response_model=AppCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_app(
    payload: AppCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AppCreatedOut:
    count = await db.scalar(select(func.count()).select_from(OAuthClient)) or 0
    max_apps = limits_for_tenant(admin.tenant).max_apps if admin.tenant else 3
    if count >= max_apps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="app_limit_reached")

    secret = new_client_secret()
    client = OAuthClient(
        tenant_id=admin.tenant_id,
        name=payload.name,
        client_id=new_client_id(),
        client_secret_hash=hash_secret(secret),
        redirect_uris=payload.redirect_uris,
        launch_url=payload.launch_url,
        access_policy=payload.access_policy,
        created_by=admin.id,
    )
    db.add(client)
    await db.flush()
    db.add(OAuthClientLookup(client_id=client.client_id, tenant_id=admin.tenant_id))
    await record_app_event(
        db,
        tenant_id=admin.tenant_id,
        event_type=AuditEventType.app_created,
        email=admin.email,
        user_id=admin.id,
        idp=admin.idp,
        request=request,
        details={"app": client.name, "policy": client.access_policy.value},
    )
    out = _to_out(client, 0)
    await db.commit()
    return AppCreatedOut(**out.model_dump(), client_secret=secret)


@router.patch("/{app_id}", response_model=AppOut)
async def patch_app(
    app_id: UUID,
    payload: AppPatch,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AppOut:
    client = await _load(db, app_id)
    if payload.name is not None:
        client.name = payload.name
    if payload.redirect_uris is not None:
        client.redirect_uris = payload.redirect_uris
    if payload.clear_launch_url:
        client.launch_url = None
    elif payload.launch_url is not None:
        client.launch_url = payload.launch_url
    if payload.access_policy is not None:
        client.access_policy = payload.access_policy
    if payload.disabled is not None:
        client.disabled_at = datetime.now(UTC) if payload.disabled else None
    await db.flush()
    counts = await _grant_counts(db, [client.id])
    out = _to_out(client, counts.get(client.id, 0))
    await db.commit()
    return out


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app(
    app_id: UUID,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    client = await _load(db, app_id)
    name = client.name
    lookup = await db.scalar(
        select(OAuthClientLookup).where(OAuthClientLookup.client_id == client.client_id)
    )
    if lookup is not None:
        await db.delete(lookup)
    await db.delete(client)
    await record_app_event(
        db,
        tenant_id=admin.tenant_id,
        event_type=AuditEventType.app_deleted,
        email=admin.email,
        user_id=admin.id,
        idp=admin.idp,
        request=request,
        details={"app": name},
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{app_id}/rotate-secret", response_model=SecretOut)
async def rotate_secret(
    app_id: UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> SecretOut:
    client = await _load(db, app_id)
    secret = new_client_secret()
    client.client_secret_hash = hash_secret(secret)
    await db.commit()
    return SecretOut(client_secret=secret)


def _normalize_grant_email(raw: str, workspace_domain: str) -> str:
    email = raw.strip().lower()
    if "@" not in email or len(email) > 320:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_email")
    local, _, domain = email.partition("@")
    if not local or not domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_email")
    try:
        normalized = normalize_workspace_domain(domain)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_email") from None
    if normalized != workspace_domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email_domain_mismatch")
    return f"{local}@{normalized}"


@router.get("/{app_id}/grants", response_model=GrantsOut)
async def list_grants(
    app_id: UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> GrantsOut:
    client = await _load(db, app_id)
    user_ids = list(
        (await db.scalars(select(AppGrant.user_id).where(AppGrant.client_pk == client.id))).all()
    )
    pending = list(
        (
            await db.scalars(
                select(PendingAppGrant.email).where(PendingAppGrant.client_pk == client.id)
            )
        ).all()
    )
    return GrantsOut(user_ids=sorted(user_ids, key=str), pending_emails=sorted(pending))


@router.put("/{app_id}/grants", response_model=GrantsOut)
async def set_grants(
    app_id: UUID,
    payload: GrantsIn,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> GrantsOut:
    """Replace assigned users and pending emails. Adds/removes are audited."""
    client = await _load(db, app_id)
    tenant = admin.tenant
    workspace_domain = tenant.workspace_domain if tenant is not None else ""
    if not workspace_domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_missing")

    wanted = set(payload.user_ids)
    wanted_emails = {_normalize_grant_email(e, workspace_domain) for e in payload.emails}

    # Only users in this tenant can be granted (RLS already guarantees the query scope).
    users = {
        u.id: u for u in (await db.scalars(select(User).where(User.id.in_(wanted)))).all()
    } if wanted else {}
    unknown = wanted - set(users)
    if unknown:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_not_found")

    # If an email already belongs to a user in the tenant, promote to a real grant.
    if wanted_emails:
        existing_by_email = {
            u.email: u
            for u in (
                await db.scalars(select(User).where(User.email.in_(wanted_emails)))
            ).all()
        }
        for email, user in existing_by_email.items():
            wanted.add(user.id)
            users[user.id] = user
            wanted_emails.discard(email)

    existing = {
        g.user_id: g
        for g in (await db.scalars(select(AppGrant).where(AppGrant.client_pk == client.id))).all()
    }

    for user_id in wanted - set(existing):
        target = users[user_id]
        db.add(
            AppGrant(
                tenant_id=admin.tenant_id,
                client_pk=client.id,
                user_id=user_id,
                granted_by=admin.id,
            )
        )
        await record_app_event(
            db,
            tenant_id=admin.tenant_id,
            event_type=AuditEventType.app_access_granted,
            email=target.email,
            user_id=target.id,
            idp=admin.idp,
            request=request,
            details={"app": client.name, "by": admin.email},
        )

    removed_ids = set(existing) - wanted
    if removed_ids:
        removed_users = {
            u.id: u
            for u in (await db.scalars(select(User).where(User.id.in_(removed_ids)))).all()
        }
        for user_id in removed_ids:
            await db.delete(existing[user_id])
            target = removed_users.get(user_id)
            await record_app_event(
                db,
                tenant_id=admin.tenant_id,
                event_type=AuditEventType.app_access_revoked,
                email=target.email if target else "unknown",
                user_id=user_id if target else None,
                idp=admin.idp,
                request=request,
                details={"app": client.name, "by": admin.email},
            )

    existing_pending = {
        p.email: p
        for p in (
            await db.scalars(
                select(PendingAppGrant).where(PendingAppGrant.client_pk == client.id)
            )
        ).all()
    }
    for email in wanted_emails - set(existing_pending):
        db.add(
            PendingAppGrant(
                tenant_id=admin.tenant_id,
                client_pk=client.id,
                email=email,
                granted_by=admin.id,
            )
        )
        await record_app_event(
            db,
            tenant_id=admin.tenant_id,
            event_type=AuditEventType.app_access_granted,
            email=email,
            user_id=None,
            idp=admin.idp,
            request=request,
            details={"app": client.name, "by": admin.email, "pending": True},
        )

    for email in set(existing_pending) - wanted_emails:
        await db.delete(existing_pending[email])
        await record_app_event(
            db,
            tenant_id=admin.tenant_id,
            event_type=AuditEventType.app_access_revoked,
            email=email,
            user_id=None,
            idp=admin.idp,
            request=request,
            details={"app": client.name, "by": admin.email, "pending": True},
        )

    await db.commit()
    return GrantsOut(
        user_ids=sorted(wanted, key=str),
        pending_emails=sorted(wanted_emails),
    )
