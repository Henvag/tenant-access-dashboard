from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.auth.audit import record_login, record_login_failure
from app.auth.identity import (
    LoginError,
    email_from_oidc_claims,
    upsert_user_from_oidc,
    write_login_session,
)
from app.auth.oidc import PROVIDERS
from app.config import settings
from app.db import get_db
from app.models import User
from app.models.user import IdentityProvider
from app.oauth.pending import PENDING_AUTHORIZE_KEY
from app.rate_limit import rate_limit_auth
from app.schemas.user import MeOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _microsoft_claims_options() -> dict:
    # /common and /consumers mint tokens whose iss is the real tenant GUID.
    return {
        "iss": {"essential": True},
        "aud": {"essential": True, "value": settings.entra_client_id},
        "exp": {"essential": True},
    }


def _frontend_redirect(*, error: str | None = None) -> RedirectResponse:
    query = urlencode({"error": error}) if error else ""
    location = settings.public_origin + "/"
    if query:
        location = f"{location}?{query}"
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
    _: None = Depends(rate_limit_auth),
):
    """Start OIDC. Tenant is resolved from email domain after callback."""
    provider = provider.strip().lower()
    if provider not in PROVIDERS or not _provider_configured(provider):
        return _frontend_redirect(error="oidc_failed")

    request.session["oidc_provider"] = provider
    client = _oauth_client(request, provider)
    return await client.authorize_redirect(request, settings.resolved_redirect_uri)


@router.get("/callback")
async def callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(rate_limit_auth),
):
    provider = (request.session.pop("oidc_provider", None) or "google").lower()
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

    email = email_from_oidc_claims(userinfo)
    oidc_sub = userinfo.get("sub")
    idp = IdentityProvider.microsoft if provider == "microsoft" else IdentityProvider.google
    hosted_domain = userinfo.get("hd") if provider == "google" else None

    if not email or not oidc_sub:
        return _frontend_redirect(error="missing_claims")

    if provider == "google" and userinfo.get("email_verified") is False:
        await record_login_failure(
            db,
            email=email,
            idp=idp,
            error_code="unverified_email",
            request=request,
            hosted_domain=hosted_domain,
        )
        await db.commit()
        return _frontend_redirect(error="unverified_email")

    try:
        user = await upsert_user_from_oidc(
            db,
            email=email,
            idp=idp,
            oidc_sub=str(oidc_sub),
            display_name=userinfo.get("name"),
            hosted_domain=hosted_domain,
        )
        await record_login(db, user=user, idp=idp, request=request)
        await db.commit()
    except LoginError as exc:
        await db.rollback()
        await record_login_failure(
            db,
            email=email,
            idp=idp,
            error_code=exc.code,
            request=request,
            hosted_domain=hosted_domain,
        )
        await db.commit()
        return _frontend_redirect(error=exc.code)
    except IntegrityError:
        await db.rollback()
        await record_login_failure(
            db,
            email=email,
            idp=idp,
            error_code="identity_conflict",
            request=request,
            hosted_domain=hosted_domain,
        )
        await db.commit()
        return _frontend_redirect(error="identity_conflict")

    # An app sign-in (/oauth/authorize) may have parked its request before login.
    pending_authorize = request.session.get(PENDING_AUTHORIZE_KEY)
    write_login_session(request.session, user)
    if pending_authorize:
        return RedirectResponse(
            f"{settings.public_origin}/oauth/authorize?{pending_authorize}",
            status_code=status.HTTP_302_FOUND,
        )
    return _frontend_redirect()


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
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
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return _frontend_redirect()
