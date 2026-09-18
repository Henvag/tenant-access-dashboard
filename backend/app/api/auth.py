from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.auth.identity import LoginError, upsert_user_from_oidc, write_login_session
from app.config import settings
from app.db import get_db
from app.models import User
from app.schemas.user import MeOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _frontend_redirect(*, error: str | None = None) -> RedirectResponse:
    query = urlencode({"error": error}) if error else ""
    location = settings.public_origin + "/"
    if query:
        location = f"{location}?{query}"
    return RedirectResponse(location, status_code=status.HTTP_302_FOUND)


@router.get("/login")
async def login(request: Request):
    """Start Google Workspace OIDC. Tenant is resolved from email domain after callback."""
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OIDC is not configured",
        )
    return await request.app.state.oauth.google.authorize_redirect(
        request, settings.resolved_redirect_uri
    )


@router.get("/callback")
async def callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        token = await request.app.state.oauth.google.authorize_access_token(request)
    except Exception:
        return _frontend_redirect(error="oidc_failed")

    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").strip().lower()
    google_sub = userinfo.get("sub")
    if not email or not google_sub:
        return _frontend_redirect(error="missing_claims")
    if userinfo.get("email_verified") is False:
        return _frontend_redirect(error="unverified_email")

    try:
        user = await upsert_user_from_oidc(
            db,
            email=email,
            google_sub=str(google_sub),
            display_name=userinfo.get("name"),
            hosted_domain=userinfo.get("hd"),
        )
        await db.commit()
    except LoginError as exc:
        await db.rollback()
        return _frontend_redirect(error=exc.code)
    except IntegrityError:
        await db.rollback()
        return _frontend_redirect(error="identity_conflict")

    write_login_session(request.session, user)
    return _frontend_redirect()


@router.get("/me", response_model=MeOut)
async def me(user: User = Depends(get_current_user)) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=user.tenant.name,
        workspace_domain=user.tenant.workspace_domain,
        last_login_at=user.last_login_at,
    )


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return _frontend_redirect()
