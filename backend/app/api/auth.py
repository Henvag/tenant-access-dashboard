from datetime import UTC, datetime
from time import time
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.auth.audit import record_login, record_login_failure
from app.auth.identity import (
    LoginError,
    email_from_oidc_claims,
    google_verified_email,
    is_managed_account,
    microsoft_verified_email,
    upsert_user_from_oidc,
    write_login_session,
)
from app.auth.oidc import PROVIDERS
from app.auth.partners import (
    PartnerError,
    companies_for_identity,
    first_partner_user,
    join_partner_companies,
    switch_company,
)
from app.config import settings
from app.db import get_db
from app.demo import (
    DEMO_SESSION_KEY,
    database_enforces_rls,
    ensure_demo_owner,
    is_demo_session,
)
from app.models import User
from app.models.user import IdentityProvider
from app.oauth.pending import PENDING_AUTHORIZE_KEY
from app.rate_limit import rate_limit_auth
from app.schemas.user import MeOut

router = APIRouter(prefix="/auth", tags=["auth"])

# "Register company" starts a normal sign-in carrying the company name; the
# tenant is created for the verified email domain once the IdP confirms it.
SIGNUP_COMPANY_KEY = "signup_company"
MAX_COMPANY_NAME = 200


def _microsoft_claims_options() -> dict:
    # /common and /consumers mint tokens whose iss is the real tenant GUID.
    return {
        "iss": {"essential": True},
        "aud": {"essential": True, "value": settings.entra_client_id},
        "exp": {"essential": True},
    }


def _frontend_redirect(*, error: str | None = None) -> RedirectResponse:
    # A normal navigation back to "/" can reuse a cached index.html from
    # before Agents and Organization existed. A refresh bypasses that cache,
    # which is why the tabs appear only then. A unique query is a new
    # document, so the browser has to load the current shell.
    params: dict[str, str] = {}
    if error:
        params["error"] = error
    params["_"] = str(int(time()))
    location = f"{settings.public_origin}/?{urlencode(params)}"
    return RedirectResponse(location, status_code=status.HTTP_302_FOUND)


def _provider_configured(provider: str) -> bool:
    if provider == "google":
        return bool(settings.google_client_id and settings.google_client_secret)
    if provider == "microsoft":
        return bool(settings.entra_client_id and settings.entra_client_secret)
    return False


def _oauth_client(request: Request, provider: str):
    oauth = request.app.state.oauth
    client = getattr(oauth, provider, None)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{provider} OIDC is not configured",
        )
    return client


@router.get("/login")
async def login(
    request: Request,
    provider: str = "google",
    company: str | None = None,
    _: None = Depends(rate_limit_auth),
):
    """Start OIDC. Tenant is resolved from the verified email after callback.

    ``company`` marks a "Register company" sign-in: the tenant is created for
    the person's verified domain (or private workspace) if none exists yet.
    """
    provider = provider.strip().lower()
    if provider not in PROVIDERS or not _provider_configured(provider):
        return _frontend_redirect(error="oidc_failed")

    request.session["oidc_provider"] = provider
    company_name = (company or "").strip()
    if company_name and len(company_name) <= MAX_COMPANY_NAME:
        request.session[SIGNUP_COMPANY_KEY] = company_name
    else:
        request.session.pop(SIGNUP_COMPANY_KEY, None)
    client = _oauth_client(request, provider)
    return await client.authorize_redirect(request, settings.resolved_redirect_uri)


@router.get("/callback")
async def callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth),
):
    provider = (request.session.pop("oidc_provider", None) or "google").lower()
    signup_company = request.session.pop(SIGNUP_COMPANY_KEY, None)
    if provider not in PROVIDERS or not _provider_configured(provider):
        return _frontend_redirect(error="oidc_failed")

    client = _oauth_client(request, provider)
    try:
        if provider == "microsoft":
            token = await client.authorize_access_token(
                request,
                claims_options=_microsoft_claims_options(),
            )
        else:
            token = await client.authorize_access_token(request)
    except Exception:
        return _frontend_redirect(error="oidc_failed")

    userinfo = token.get("userinfo") or {}
    if not userinfo and provider == "microsoft":
        try:
            userinfo = await client.userinfo(token=token)
        except Exception:
            userinfo = {}

    claimed_email = email_from_oidc_claims(userinfo)
    oidc_sub = userinfo.get("sub")
    idp = IdentityProvider.microsoft if provider == "microsoft" else IdentityProvider.google
    hosted_domain = userinfo.get("hd") if provider == "google" else None

    if not claimed_email or not oidc_sub:
        return _frontend_redirect(error="missing_claims")

    # Tenant membership and account matching both hang off the email, so only
    # an address the IdP vouches for may be used.
    if provider == "google":
        email = google_verified_email(userinfo)
    else:
        email = microsoft_verified_email(userinfo)
    if email is None:
        if provider == "google":
            await record_login_failure(
                db,
                email=claimed_email,
                idp=idp,
                error_code="unverified_email",
                request=request,
                hosted_domain=hosted_domain,
            )
            await db.commit()
        # An unverified Microsoft address is attacker-chosen, so it must not
        # write into the audit log of whichever company owns that domain.
        return _frontend_redirect(error="unverified_email")

    user: User | None = None
    home_error: str | None = None
    try:
        user = await upsert_user_from_oidc(
            db,
            email=email,
            idp=idp,
            oidc_sub=str(oidc_sub),
            display_name=userinfo.get("name"),
            hosted_domain=hosted_domain,
            new_tenant_name=signup_company,
            managed_account=is_managed_account(idp, userinfo),
        )
        await record_login(db, user=user, idp=idp, request=request)
        await db.commit()
    except LoginError as exc:
        await db.rollback()
        home_error = exc.code
    except IntegrityError:
        await db.rollback()
        home_error = "identity_conflict"

    # Partner mode: accept open invites to other companies for this verified
    # address. Someone whose own domain has no company (no_tenant) may still
    # sign in to a company that invited them as an outside admin.
    await join_partner_companies(
        db,
        email=email,
        idp=idp,
        oidc_sub=str(oidc_sub),
        display_name=userinfo.get("name"),
        request=request,
    )
    await db.commit()
    if home_error == "no_tenant":
        user = await first_partner_user(db, idp=idp, oidc_sub=str(oidc_sub))
        if user is not None:
            user.display_name = userinfo.get("name") or user.display_name
            user.last_login_at = datetime.now(UTC)
            await record_login(db, user=user, idp=idp, request=request)
            await db.commit()
            home_error = None

    if user is None or home_error is not None:
        code = home_error or "no_tenant"
        await record_login_failure(
            db,
            email=email,
            idp=idp,
            error_code=code,
            request=request,
            hosted_domain=hosted_domain,
        )
        await db.commit()
        return _frontend_redirect(error=code)

    # An app sign-in (/oauth/authorize) may have parked its request before login.
    pending_authorize = request.session.get(PENDING_AUTHORIZE_KEY)
    write_login_session(request.session, user)
    if pending_authorize:
        return RedirectResponse(
            f"{settings.public_origin}/oauth/authorize?{pending_authorize}",
            status_code=status.HTTP_302_FOUND,
        )
    return _frontend_redirect()


@router.post("/demo")
async def demo_login(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth),
):
    """Sign in to the public read-only sample company. No IdP, no audit row."""
    if not settings.demo_enabled or not await database_enforces_rls(db):
        return _frontend_redirect(error="demo_unavailable")
    owner = await ensure_demo_owner(db)
    await db.commit()
    # Drop any parked app sign-in: it belonged to whoever was here before.
    request.session.clear()
    write_login_session(request.session, owner)
    request.session[DEMO_SESSION_KEY] = True
    return RedirectResponse(
        f"{settings.public_origin}/?_={int(time())}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/me", response_model=MeOut)
async def me(request: Request, user: User = Depends(get_current_user)) -> MeOut:
    from app.billing.plans import effective_plan_id, limits_for_tenant

    limits = limits_for_tenant(user.tenant)
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=user.tenant.name,
        workspace_domain=user.tenant.workspace_domain,
        last_login_at=user.last_login_at,
        disabled=user.disabled,
        is_owner=user.tenant.owner_user_id is not None
        and user.id == user.tenant.owner_user_id,
        plan=effective_plan_id(user.tenant).value,
        max_apps=limits.max_apps,
        max_users=limits.max_users,
        audit_retention_days=limits.audit_retention_days,
        has_logo=bool(user.tenant.logo_bytes),
        has_ask=bool(user.tenant.ask_secret),
        demo=is_demo_session(request.session),
        external=user.external,
    )


class CompanyOut(BaseModel):
    tenant_id: UUID
    name: str
    workspace_domain: str
    current: bool


class SwitchIn(BaseModel):
    tenant_id: UUID


@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CompanyOut]:
    """Every company the signed-in identity belongs to (partner mode)."""
    rows = await companies_for_identity(db, idp=user.idp, oidc_sub=user.oidc_sub)
    out = [
        CompanyOut(tenant_id=tid, name=name, workspace_domain=domain, current=tid == user.tenant_id)
        for tid, name, domain in rows
    ]
    if not any(c.current for c in out):
        out.insert(
            0,
            CompanyOut(
                tenant_id=user.tenant_id,
                name=user.tenant.name,
                workspace_domain=user.tenant.workspace_domain,
                current=True,
            ),
        )
    return out


@router.post("/switch")
async def switch(
    body: SwitchIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Work in another company this identity belongs to. Starts a new session."""
    try:
        target = await switch_company(db, current=user, tenant_id=body.tenant_id, request=request)
    except PartnerError as exc:
        code = status.HTTP_403_FORBIDDEN if exc.code == "user_disabled" else status.HTTP_404_NOT_FOUND
        raise HTTPException(status_code=code, detail=exc.code) from None
    await db.commit()
    # A parked app sign-in belonged to the previous company; drop it.
    request.session.pop(PENDING_AUTHORIZE_KEY, None)
    write_login_session(request.session, target)
    return {"tenant_id": str(target.tenant_id)}


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return _frontend_redirect()
