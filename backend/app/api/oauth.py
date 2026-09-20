"""OIDC provider endpoints: discovery, JWKS, authorize, token, userinfo.

Flow for a registered app ("relying party", e.g. Grafana):
  1. RP sends the browser to /oauth/authorize with PKCE.
  2. If the user has no dashboard session we park the request and send them to
     the landing page; /auth/callback resumes it after Google/Microsoft sign-in.
  3. We check tenant, disabled state and the app's access policy, audit the
     decision, and redirect back with a single-use code (or to a denial page).
  4. RP exchanges the code at /oauth/token (client secret + PKCE verifier) and
     receives an RS256 ID token + access token carrying email, name and role.
  5. RP may call /oauth/userinfo with the access token.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Header, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.audit import record_app_event
from app.auth.identity import read_login_session
from app.auth.rls import set_tenant_rls
from app.config import settings
from app.db import get_db
from app.models import (
    AuditEventType,
    IdentityProvider,
    OAuthClient,
    OAuthClientLookup,
    Tenant,
    User,
)
from app.oauth import keys
from app.oauth.pending import PENDING_AUTHORIZE_KEY
from app.oauth.service import (
    SUPPORTED_SCOPES,
    TOKEN_TTL,
    access_denial_reason,
    consume_code,
    issue_code,
    purge_expired_codes,
    role_claim,
    verify_secret,
)
from app.rate_limit import rate_limit_token

router = APIRouter(tags=["oidc-provider"])


def issuer() -> str:
    return settings.public_origin


# ---------- discovery ----------


@router.get("/.well-known/openid-configuration")
async def openid_configuration() -> dict:
    base = issuer()
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "userinfo_endpoint": f"{base}/oauth/userinfo",
        "jwks_uri": f"{base}/.well-known/jwks.json",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": [keys.ALG],
        "scopes_supported": sorted(SUPPORTED_SCOPES),
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
        "claims_supported": [
            "sub",
            "iss",
            "aud",
            "exp",
            "iat",
            "email",
            "email_verified",
            "name",
            "preferred_username",
            "role",
            "tenant",
            "tenant_id",
        ],
    }


@router.get("/.well-known/jwks.json")
async def jwks(db: AsyncSession = Depends(get_db)) -> dict:
    return await keys.public_jwks(db)


# ---------- authorize ----------


def _frontend(path_query: dict[str, str]) -> RedirectResponse:
    location = settings.public_origin + "/"
    if path_query:
        location += "?" + urlencode(path_query)
    return RedirectResponse(location, status_code=status.HTTP_302_FOUND)


def _rp_error(redirect_uri: str, error: str, state: str | None, description: str) -> RedirectResponse:
    params = {"error": error, "error_description": description}
    if state:
        params["state"] = state
    return RedirectResponse(f"{redirect_uri}?{urlencode(params)}", status_code=302)


async def _resolve_client(db: AsyncSession, client_id: str) -> OAuthClient | None:
    """Public lookup → scope RLS → load the protected client row."""
    lookup = await db.scalar(
        select(OAuthClientLookup).where(OAuthClientLookup.client_id == client_id)
    )
    if lookup is None:
        return None
    await set_tenant_rls(db, lookup.tenant_id)
    return await db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))


@router.get("/oauth/authorize")
async def authorize(request: Request, db: AsyncSession = Depends(get_db)):
    q = request.query_params
    client_id = q.get("client_id", "")
    redirect_uri = q.get("redirect_uri", "")
    state = q.get("state")

    client = await _resolve_client(db, client_id) if client_id else None
    if client is None:
        return _frontend({"error": "app_unknown_client"})
    if redirect_uri not in client.redirect_uris:
        # Never redirect to an unregistered URI.
        return _frontend({"error": "app_invalid_redirect", "app": client.name})

    if q.get("response_type") != "code":
        return _rp_error(redirect_uri, "unsupported_response_type", state, "only code is supported")
    scope_set = set((q.get("scope") or "openid").split())
    if "openid" not in scope_set or not scope_set <= SUPPORTED_SCOPES:
        return _rp_error(redirect_uri, "invalid_scope", state, "supported: openid email profile")
    code_challenge = q.get("code_challenge", "")
    code_challenge_method = q.get("code_challenge_method", "S256")
    # Outline's passport-oauth2 plugin does not send PKCE. Confidential clients
    # (all of ours use a client secret) may omit it; if a challenge is sent it
    # must be S256.
    if code_challenge and code_challenge_method != "S256":
        return _rp_error(redirect_uri, "invalid_request", state, "PKCE method must be S256")
    if not code_challenge:
        code_challenge_method = ""


    identities = read_login_session(request.session)
    if identities is None:
        # Park the full request; /auth/callback resumes it after sign-in.
        request.session[PENDING_AUTHORIZE_KEY] = str(request.url.query)
        return _frontend({"continue": client.name})

    session_user_id, session_tenant_id = identities
    request.session.pop(PENDING_AUTHORIZE_KEY, None)
    if session_tenant_id != client.tenant_id:
        # Cross-tenant attempt: we cannot even audit into the client's tenant with
        # the actor's identity, so deny with the reason and record it under the app's tenant.
        await record_app_event(
            db,
            tenant_id=client.tenant_id,
            event_type=AuditEventType.app_login_denied,
            email="unknown@other-tenant",
            idp=IdentityProvider.google,
            request=request,
            error_code="wrong_tenant",
            details={"app": client.name, "reason": "wrong_tenant"},
        )
        await db.commit()
        return _frontend({"error": "app_access_denied", "app": client.name, "reason": "wrong_tenant"})

    user = await db.scalar(select(User).where(User.id == session_user_id))
    if user is None:
        request.session.clear()
        request.session[PENDING_AUTHORIZE_KEY] = str(request.url.query)
        return _frontend({"continue": client.name})

    reason = await access_denial_reason(db, client=client, user=user)
    if reason is not None:
        await record_app_event(
            db,
            tenant_id=client.tenant_id,
            event_type=AuditEventType.app_login_denied,
            email=user.email,
            user_id=user.id,
            idp=user.idp,
            request=request,
            error_code=reason,
            details={"app": client.name, "reason": reason},
        )
        await db.commit()
        return _frontend({"error": "app_access_denied", "app": client.name, "reason": reason})

    code = await issue_code(
        db,
        client=client,
        user=user,
        redirect_uri=redirect_uri,
        scope=" ".join(sorted(scope_set)),
        nonce=q.get("nonce"),
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    await record_app_event(
        db,
        tenant_id=client.tenant_id,
        event_type=AuditEventType.app_login,
        email=user.email,
        user_id=user.id,
        idp=user.idp,
        request=request,
        details={"app": client.name},
    )
    await purge_expired_codes(db, client.tenant_id)
    await db.commit()

    params = {"code": code}
    if state:
        params["state"] = state
    return RedirectResponse(f"{redirect_uri}?{urlencode(params)}", status_code=302)


@router.get("/oauth/resume")
async def resume_authorize(request: Request):
    """Resume a parked authorize request after the SPA loaded a logged-in session.

    Outline (and other RPs) send the browser to /oauth/authorize; if we parked
    because the session cookie was missing on that hop, the SPA may still have
    a valid login. The frontend sends the user here to finish the RP redirect.
    """
    pending = request.session.get(PENDING_AUTHORIZE_KEY)
    if not pending:
        return _frontend({})
    return RedirectResponse(
        f"{settings.public_origin}/oauth/authorize?{pending}",
        status_code=status.HTTP_302_FOUND,
    )


# ---------- token ----------


def _token_error(error: str, description: str, http_status: int = 400) -> JSONResponse:
    return JSONResponse(
        {"error": error, "error_description": description},
        status_code=http_status,
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


def _client_credentials(
    authorization: str | None, client_id: str | None, client_secret: str | None
) -> tuple[str, str] | None:
    if authorization and authorization.lower().startswith("basic "):
        try:
            raw = base64.b64decode(authorization[6:]).decode()
            cid, secret = raw.split(":", 1)
            return cid, secret
        except (ValueError, UnicodeDecodeError):
            return None
    if client_id and client_secret:
        return client_id, client_secret
    return None


@router.post("/oauth/token")
async def token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _rl: None = Depends(rate_limit_token),
    grant_type: str = Form(""),
    code: str = Form(""),
    redirect_uri: str = Form(""),
    code_verifier: str = Form(""),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    authorization: str | None = Header(None),
):
    if grant_type != "authorization_code":
        return _token_error("unsupported_grant_type", "only authorization_code is supported")

    creds = _client_credentials(authorization, client_id, client_secret)
    if creds is None:
        return _token_error("invalid_client", "client authentication required", 401)
    cid, secret = creds

    client = await _resolve_client(db, cid)
    if client is None or client.disabled or not verify_secret(secret, client.client_secret_hash):
        return _token_error("invalid_client", "unknown client or bad secret", 401)

    if not code or not redirect_uri:
        return _token_error("invalid_request", "code and redirect_uri are required")

    row = await consume_code(
        db, code=code, client=client, redirect_uri=redirect_uri, code_verifier=code_verifier
    )
    if row is None:
        await db.commit()
        return _token_error("invalid_grant", "code is invalid, expired, or already used")

    user = await db.scalar(select(User).where(User.id == row.user_id))
    tenant = await db.scalar(select(Tenant).where(Tenant.id == client.tenant_id))
    if user is None or tenant is None or user.disabled:
        await db.commit()
        return _token_error("invalid_grant", "user is no longer allowed to sign in")

    await db.commit()

    now = datetime.now(UTC)
    exp = now + TOKEN_TTL
    iss = issuer()
    key = await keys.active_key(db)
    profile = {
        "email": user.email,
        "email_verified": True,
        "name": user.display_name or user.email.split("@")[0],
        # Outline and similar RPs default to preferred_username for the login handle.
        "preferred_username": user.email,
        "role": role_claim(user, tenant),
        "tenant": tenant.name,
        "tenant_id": str(tenant.id),
    }
    id_claims = {
        "iss": iss,
        "sub": str(user.id),
        "aud": client.client_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "auth_time": int(now.timestamp()),
        **profile,
    }
    if row.nonce:
        id_claims["nonce"] = row.nonce
    access_claims = {
        "iss": iss,
        "sub": str(user.id),
        "aud": f"{iss}/oauth/userinfo",
        "client_id": client.client_id,
        "scope": row.scope,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "tenant_id": str(tenant.id),
    }
    return JSONResponse(
        {
            "access_token": keys.sign(key, access_claims, typ="at+jwt"),
            "token_type": "Bearer",
            "expires_in": int(TOKEN_TTL.total_seconds()),
            "id_token": keys.sign(key, id_claims),
            "scope": row.scope,
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


# ---------- userinfo ----------


@router.get("/oauth/userinfo")
async def userinfo(
    response: Response,
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(None),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        return _token_error("invalid_token", "bearer token required", 401)
    claims = await keys.verify(db, authorization[7:].strip(), issuer=issuer())
    if not claims or claims.get("aud") != f"{issuer()}/oauth/userinfo":
        return _token_error("invalid_token", "token is invalid or expired", 401)

    try:
        tenant_id = UUID(str(claims.get("tenant_id")))
        user_id = UUID(str(claims.get("sub")))
    except ValueError:
        return _token_error("invalid_token", "malformed claims", 401)

    await set_tenant_rls(db, tenant_id)
    user = await db.scalar(select(User).where(User.id == user_id))
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if user is None or tenant is None or user.disabled:
        return _token_error("invalid_token", "user is no longer allowed to sign in", 401)

    response.headers["Cache-Control"] = "no-store"
    return {
        "sub": str(user.id),
        "email": user.email,
        "email_verified": True,
        "name": user.display_name or user.email.split("@")[0],
        "preferred_username": user.email,
        "role": role_claim(user, tenant),
        "tenant": tenant.name,
        "tenant_id": str(tenant.id),
    }
