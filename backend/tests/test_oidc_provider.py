"""End-to-end tests for the OIDC provider: app registration, grants, code flow, tokens."""

import base64
import hashlib
import json
import secrets
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from itsdangerous import TimestampSigner
from joserfc import jwt
from joserfc.jwk import KeySet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import main
from app.auth.rls import set_tenant_rls
from app.config import settings
from app.db import get_db
from app.models import AuditEvent, AuditEventType, IdentityProvider, Tenant, User, UserRole
from app.oauth import keys

pytestmark = pytest.mark.asyncio

REDIRECT = "https://grafana.example.com/login/generic_oauth"


def _session_cookie(user: User) -> str:
    """Forge the Starlette session cookie the same way SessionMiddleware does."""
    payload = {
        "user_id": str(user.id),
        "tenant_id": str(user.tenant_id),
        "role": user.role.value,
    }
    data = base64.b64encode(json.dumps(payload).encode())
    return TimestampSigner(settings.session_secret).sign(data).decode()


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


async def _seed(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[Tenant, User, User]:
    suffix = uuid4().hex[:8]
    domain = f"oidc-{suffix}.com"
    async with factory() as session:
        tenant = Tenant(name=f"OIDC Co {suffix}", workspace_domain=domain)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

    async with factory() as session:
        await set_tenant_rls(session, tenant.id)
        admin = User(
            tenant_id=tenant.id,
            email=f"admin@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"admin-{suffix}",
            role=UserRole.admin,
            display_name="Ada Admin",
        )
        member = User(
            tenant_id=tenant.id,
            email=f"member@{domain}",
            idp=IdentityProvider.microsoft,
            oidc_sub=f"member-{suffix}",
            role=UserRole.user,
            display_name="Mia Member",
        )
        session.add_all([admin, member])
        await session.flush()
        t = await session.scalar(select(Tenant).where(Tenant.id == tenant.id))
        assert t is not None
        t.owner_user_id = admin.id
        await session.commit()
    return tenant, admin, member


@pytest.fixture
async def client(
    app_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with app_session_factory() as session:
            yield session

    main.app.dependency_overrides[get_db] = override_db
    keys.reset_cache()
    transport = ASGITransport(app=main.app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=False
    ) as http:
        yield http
    main.app.dependency_overrides.pop(get_db, None)


async def _register_app(http: AsyncClient, admin: User, policy: str = "assigned") -> dict:
    response = await http.post(
        "/apps",
        json={
            "name": "Grafana",
            "redirect_uris": [REDIRECT],
            "launch_url": "https://grafana.example.com/login/generic_oauth",
            "access_policy": policy,
        },
        cookies={"session": _session_cookie(admin)},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["client_id"].startswith("tad_")
    assert len(body["client_secret"]) > 30
    return body


def _authorize_params(client_id: str, challenge: str, **extra: str) -> dict:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "scope": "openid email profile",
        "state": "xyz",
        "nonce": "n-123",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    params.update(extra)
    return params


async def test_discovery_and_jwks(client: AsyncClient):
    disco = await client.get("/.well-known/openid-configuration")
    assert disco.status_code == 200
    body = disco.json()
    assert body["issuer"] == settings.public_origin
    assert body["code_challenge_methods_supported"] == ["S256"]

    jwks = await client.get("/.well-known/jwks.json")
    assert jwks.status_code == 200
    keyset = jwks.json()["keys"]
    assert len(keyset) >= 1
    assert keyset[0]["kty"] == "RSA" and keyset[0]["alg"] == "RS256" and keyset[0]["kid"]


async def test_full_code_flow_with_grants(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
):
    tenant, admin, member = await _seed(app_session_factory)
    app = await _register_app(client, admin, policy="assigned")
    verifier, challenge = _pkce()
    member_cookie = {"session": _session_cookie(member)}

    # 1. Not assigned yet → denied and audited.
    denied = await client.get(
        "/oauth/authorize", params=_authorize_params(app["client_id"], challenge), cookies=member_cookie
    )
    assert denied.status_code == 302
    location = denied.headers["location"]
    assert location.startswith(settings.public_origin + "/?")
    q = parse_qs(urlsplit(location).query)
    assert q["error"] == ["app_access_denied"] and q["reason"] == ["not_assigned"]

    # 2. Admin grants the member.
    granted = await client.put(
        f"/apps/{app['id']}/grants",
        json={"user_ids": [str(member.id)]},
        cookies={"session": _session_cookie(admin)},
    )
    assert granted.status_code == 200 and granted.json() == [str(member.id)]

    # 3. Authorize succeeds with a code.
    ok = await client.get(
        "/oauth/authorize", params=_authorize_params(app["client_id"], challenge), cookies=member_cookie
    )
    assert ok.status_code == 302
    location = ok.headers["location"]
    assert location.startswith(REDIRECT + "?")
    q = parse_qs(urlsplit(location).query)
    code = q["code"][0]
    assert q["state"] == ["xyz"]

    # 4. Token exchange with HTTP Basic client auth + PKCE.
    basic = base64.b64encode(f"{app['client_id']}:{app['client_secret']}".encode()).decode()
    tok = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
        },
        headers={"Authorization": f"Basic {basic}"},
    )
    assert tok.status_code == 200, tok.text
    tokens = tok.json()
    assert tokens["token_type"] == "Bearer"

    jwks = (await client.get("/.well-known/jwks.json")).json()
    keyset = KeySet.import_key_set(jwks)
    id_claims = jwt.decode(tokens["id_token"], keyset, algorithms=["RS256"]).claims
    assert id_claims["iss"] == settings.public_origin
    assert id_claims["aud"] == app["client_id"]
    assert id_claims["sub"] == str(member.id)
    assert id_claims["email"] == member.email
    assert id_claims["name"] == "Mia Member"
    assert id_claims["role"] == "member"
    assert id_claims["nonce"] == "n-123"
    assert id_claims["tenant_id"] == str(tenant.id)

    # 5. Userinfo with the access token.
    info = await client.get(
        "/oauth/userinfo", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert info.status_code == 200
    assert info.json()["email"] == member.email and info.json()["role"] == "member"

    # 6. Code is single-use.
    again = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
        },
        headers={"Authorization": f"Basic {basic}"},
    )
    assert again.status_code == 400 and again.json()["error"] == "invalid_grant"

    # 7. Audit trail under the tenant.
    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        events = list(
            await session.scalars(select(AuditEvent).order_by(AuditEvent.created_at))
        )
        types = [e.event_type for e in events]
        assert AuditEventType.app_created in types
        assert AuditEventType.app_login_denied in types
        assert AuditEventType.app_access_granted in types
        assert AuditEventType.app_login in types
        denied_event = next(e for e in events if e.event_type == AuditEventType.app_login_denied)
        assert denied_event.error_code == "not_assigned"
        assert denied_event.details == {"app": "Grafana", "reason": "not_assigned"}


async def test_owner_role_claim_and_admins_policy(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
):
    _tenant, admin, member = await _seed(app_session_factory)
    app = await _register_app(client, admin, policy="admins")
    verifier, challenge = _pkce()

    # Member blocked by admins-only policy.
    denied = await client.get(
        "/oauth/authorize",
        params=_authorize_params(app["client_id"], challenge),
        cookies={"session": _session_cookie(member)},
    )
    assert parse_qs(urlsplit(denied.headers["location"]).query)["reason"] == ["admins_only"]

    # Owner gets role=owner in the token (Grafana maps this to Admin).
    ok = await client.get(
        "/oauth/authorize",
        params=_authorize_params(app["client_id"], challenge),
        cookies={"session": _session_cookie(admin)},
    )
    code = parse_qs(urlsplit(ok.headers["location"]).query)["code"][0]
    tok = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
            "client_id": app["client_id"],
            "client_secret": app["client_secret"],
        },
    )
    assert tok.status_code == 200, tok.text
    jwks = (await client.get("/.well-known/jwks.json")).json()
    claims = jwt.decode(tok.json()["id_token"], KeySet.import_key_set(jwks), algorithms=["RS256"]).claims
    assert claims["role"] == "owner"


async def test_rejections(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
):
    _tenant, admin, member = await _seed(app_session_factory)
    app = await _register_app(client, admin, policy="everyone")
    verifier, challenge = _pkce()
    cookie = {"session": _session_cookie(member)}

    # Unregistered redirect URI never redirects to the RP.
    bad = await client.get(
        "/oauth/authorize",
        params=_authorize_params(app["client_id"], challenge, redirect_uri="https://evil.example/cb"),
        cookies=cookie,
    )
    assert bad.headers["location"].startswith(settings.public_origin + "/?error=app_invalid_redirect")

    # Missing PKCE → error back to the RP.
    nopkce = await client.get(
        "/oauth/authorize",
        params={k: v for k, v in _authorize_params(app["client_id"], challenge).items() if k != "code_challenge"},
        cookies=cookie,
    )
    q = parse_qs(urlsplit(nopkce.headers["location"]).query)
    assert nopkce.headers["location"].startswith(REDIRECT) and q["error"] == ["invalid_request"]

    # Not signed in → parked and sent to landing with the app name.
    anon = await client.get("/oauth/authorize", params=_authorize_params(app["client_id"], challenge))
    assert anon.headers["location"] == settings.public_origin + "/?continue=Grafana"

    # Wrong PKCE verifier burns the code.
    ok = await client.get(
        "/oauth/authorize", params=_authorize_params(app["client_id"], challenge), cookies=cookie
    )
    code = parse_qs(urlsplit(ok.headers["location"]).query)["code"][0]
    wrong = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": "not-the-right-verifier-" + "x" * 30,
            "client_id": app["client_id"],
            "client_secret": app["client_secret"],
        },
    )
    assert wrong.status_code == 400 and wrong.json()["error"] == "invalid_grant"
    retry = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
            "client_id": app["client_id"],
            "client_secret": app["client_secret"],
        },
    )
    assert retry.status_code == 400

    # Bad client secret.
    unauth = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": "whatever",
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
            "client_id": app["client_id"],
            "client_secret": "nope",
        },
    )
    assert unauth.status_code == 401 and unauth.json()["error"] == "invalid_client"


async def test_cross_tenant_isolation(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
):
    _tenant_a, admin_a, _member_a = await _seed(app_session_factory)
    _tenant_b, admin_b, member_b = await _seed(app_session_factory)
    app = await _register_app(client, admin_a, policy="everyone")
    _verifier, challenge = _pkce()

    # Tenant B's admin cannot see tenant A's apps (RLS).
    listing = await client.get("/apps", cookies={"session": _session_cookie(admin_b)})
    assert listing.status_code == 200 and listing.json() == []

    # Tenant B's user cannot sign in to tenant A's app.
    denied = await client.get(
        "/oauth/authorize",
        params=_authorize_params(app["client_id"], challenge),
        cookies={"session": _session_cookie(member_b)},
    )
    q = parse_qs(urlsplit(denied.headers["location"]).query)
    assert q["error"] == ["app_access_denied"] and q["reason"] == ["wrong_tenant"]

    # Tenant B's admin cannot grant or delete tenant A's app.
    forbidden = await client.put(
        f"/apps/{app['id']}/grants",
        json={"user_ids": [str(member_b.id)]},
        cookies={"session": _session_cookie(admin_b)},
    )
    assert forbidden.status_code == 404
    gone = await client.delete(f"/apps/{app['id']}", cookies={"session": _session_cookie(admin_b)})
    assert gone.status_code == 404


async def test_my_apps_respects_policy(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
):
    _tenant, admin, member = await _seed(app_session_factory)
    await _register_app(client, admin, policy="admins")
    mine_member = await client.get("/apps/mine", cookies={"session": _session_cookie(member)})
    mine_admin = await client.get("/apps/mine", cookies={"session": _session_cookie(admin)})
    assert mine_member.json() == []
    assert [a["name"] for a in mine_admin.json()] == ["Grafana"]
