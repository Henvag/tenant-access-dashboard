"""Slack accounts follow access in Tenant Access, against a simulated Slack SCIM API."""

import base64
import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from itsdangerous import TimestampSigner
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import main
from app.auth.rls import set_tenant_rls
from app.config import settings
from app.db import get_db
from app.models import (
    AccessPolicy,
    AppAccount,
    AppGrant,
    AuditEvent,
    AuditEventType,
    IdentityProvider,
    OAuthClient,
    ProvisionOutbox,
    Tenant,
    User,
    UserRole,
)
from app.oauth import keys
from app.provisioning import scim, worker

pytestmark = pytest.mark.asyncio

TOKEN = "xoxp-good-token"


class FakeSlack:
    """Enough of https://api.slack.com/scim/v2 to provision users."""

    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.busy = 0  # answer this many writes with 429
        self.calls: list[str] = []

    def add(self, email: str, *, active: bool = True, username: str | None = None) -> str:
        uid = f"U{len(self.users) + 1:04d}"
        self.users[uid] = {
            "id": uid,
            "userName": username or email.split("@")[0],
            "emails": [{"value": email, "primary": True}],
            "active": active,
        }
        return uid

    def by_email(self, email: str) -> dict | None:
        return next(
            (u for u in self.users.values() if u["emails"][0]["value"] == email), None
        )

    def _error(self, status: int, detail: str) -> httpx.Response:
        return httpx.Response(
            status,
            json={
                "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
                "detail": detail,
                "status": status,
            },
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(f"{request.method} {request.url.path}")
        assert request.url.host == "api.slack.com"
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return self._error(401, "invalid_authentication")
        path = request.url.path.removeprefix("/scim/v2")
        if request.method != "GET" and self.busy:
            self.busy -= 1
            return httpx.Response(429, headers={"Retry-After": "5"})
        if path == "/Users" and request.method == "GET":
            found = list(self.users.values())
            flt = request.url.params.get("filter")
            if flt:
                match = re.fullmatch(r'email eq "(.+)"', flt)
                assert match, flt
                found = [u for u in found if u["emails"][0]["value"] == match.group(1)]
            return httpx.Response(200, json={"Resources": found, "totalResults": len(found)})
        if path == "/Users" and request.method == "POST":
            body = json.loads(request.content)
            email = body["emails"][0]["value"]
            if self.by_email(email):
                return self._error(409, "email_taken")
            if any(u["userName"] == body["userName"] for u in self.users.values()):
                return self._error(409, "username_taken")
            uid = self.add(email, username=body["userName"])
            self.users[uid]["displayName"] = body.get("displayName")
            return httpx.Response(201, json=self.users[uid])
        uid = path.removeprefix("/Users/")
        user = self.users.get(uid)
        if user is None:
            return self._error(404, "no_such_user")
        if request.method == "GET":
            return httpx.Response(200, json=user)
        if request.method == "PATCH":
            body = json.loads(request.content)
            (op,) = body["Operations"]
            assert op["path"] == "active"
            user["active"] = op["value"]
            return httpx.Response(200, json=user)
        return self._error(400, "unsupported")


@pytest.fixture
def slack(monkeypatch) -> FakeSlack:
    fake = FakeSlack()
    monkeypatch.setattr(scim, "_transport", httpx.MockTransport(fake.handler))
    return fake


def _cookie(user: User) -> dict[str, str]:
    payload = {"user_id": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role.value}
    data = base64.b64encode(json.dumps(payload).encode())
    return {"session": TimestampSigner(settings.session_secret).sign(data).decode()}


@pytest.fixture
async def client(
    app_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with app_session_factory() as session:
            yield session

    main.app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=main.app), base_url="http://testserver"
    ) as http:
        yield http
    main.app.dependency_overrides.clear()


async def _seed(factory) -> tuple[Tenant, User, User, OAuthClient]:
    suffix = uuid4().hex[:8]
    domain = f"slack-{suffix}.no"
    async with factory() as session:
        await keys.active_key(session)
    async with factory() as session:
        tenant = Tenant(name=f"Slack {suffix}", workspace_domain=domain)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
    async with factory() as session:
        await set_tenant_rls(session, tenant.id)
        owner = User(
            tenant_id=tenant.id,
            email=f"owner@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"owner-{suffix}",
            role=UserRole.admin,
        )
        anna = User(
            tenant_id=tenant.id,
            email=f"anna.berg@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"anna-{suffix}",
            role=UserRole.user,
            display_name="Anna Berg",
        )
        session.add_all([owner, anna])
        await session.flush()
        (await session.get(Tenant, tenant.id)).owner_user_id = owner.id
        app = OAuthClient(
            tenant_id=tenant.id,
            name="Slack",
            client_id=f"slack-{suffix}",
            client_secret_hash="x",
            redirect_uris=[],
            access_policy=AccessPolicy.assigned,
        )
        session.add(app)
        await session.flush()
        for row in (owner, anna, app):
            await session.refresh(row)
        await session.commit()
    return tenant, owner, anna, app


async def _connect(client: AsyncClient, owner: User, app: OAuthClient) -> None:
    response = await client.put(
        f"/apps/{app.id}/provisioning",
        json={"kind": "slack", "token": TOKEN},
        cookies=_cookie(owner),
    )
    assert response.status_code == 200, response.text
    assert response.json()["provision_kind"] == "slack"


async def _grant(client: AsyncClient, owner: User, app: OAuthClient, user_ids, emails=()):
    response = await client.put(
        f"/apps/{app.id}/grants",
        json={"user_ids": [str(u) for u in user_ids], "emails": list(emails)},
        cookies=_cookie(owner),
    )
    assert response.status_code == 200, response.text


async def _drain(factory) -> None:
    for _ in range(5):
        if not await worker.run_once(factory):
            return


async def _events(factory, tenant: Tenant) -> list[AuditEvent]:
    async with factory() as session:
        await set_tenant_rls(session, tenant.id)
        return list(
            (
                await session.scalars(
                    select(AuditEvent)
                    .where(
                        AuditEvent.tenant_id == tenant.id,
                        AuditEvent.event_type == AuditEventType.app_account_changed,
                    )
                    .order_by(AuditEvent.created_at)
                )
            ).all()
        )


async def test_saving_a_token_checks_it_first(app_session_factory, client, slack):
    _tenant, owner, _anna, app = await _seed(app_session_factory)
    bad = await client.put(
        f"/apps/{app.id}/provisioning",
        json={"kind": "slack", "token": "xoxp-wrong"},
        cookies=_cookie(owner),
    )
    assert bad.status_code == 400
    assert bad.json()["detail"] == "provision_key_rejected"

    await _connect(client, owner, app)
    listed = await client.get("/apps", cookies=_cookie(owner))
    mine = next(a for a in listed.json() if a["id"] == str(app.id))
    assert mine["provision_key_hint"] == TOKEN[-4:]
    assert "token" not in json.dumps(mine).lower().replace("provision_key_hint", "")


async def test_grant_creates_and_disable_deactivates(app_session_factory, client, slack):
    tenant, owner, anna, app = await _seed(app_session_factory)
    await _connect(client, owner, app)
    await _drain(app_session_factory)
    assert slack.users == {}  # nobody has access yet

    await _grant(client, owner, app, [anna.id])
    await _drain(app_session_factory)
    created = slack.by_email(anna.email)
    assert created is not None and created["active"] is True
    assert created["userName"] == "anna.berg"
    assert created["displayName"] == "Anna Berg"

    disabled = await client.patch(
        f"/users/{anna.id}", json={"disabled": True}, cookies=_cookie(owner)
    )
    assert disabled.status_code == 200
    await _drain(app_session_factory)
    assert slack.by_email(anna.email)["active"] is False

    enabled = await client.patch(
        f"/users/{anna.id}", json={"disabled": False}, cookies=_cookie(owner)
    )
    assert enabled.status_code == 200
    await _drain(app_session_factory)
    assert slack.by_email(anna.email)["active"] is True

    await _grant(client, owner, app, [])
    await _drain(app_session_factory)
    assert slack.by_email(anna.email)["active"] is False
    assert len(slack.users) == 1

    actions = [e.details["action"] for e in await _events(app_session_factory, tenant)]
    assert actions == ["created", "deactivated", "reactivated", "deactivated"]

    accounts = await client.get(f"/apps/{app.id}/accounts", cookies=_cookie(owner))
    (row,) = accounts.json()["accounts"]
    assert row["email"] == anna.email
    assert row["status"] == "deactivated"
    assert row["queued"] is False


async def test_reactivates_an_old_slack_account_instead_of_creating(
    app_session_factory, client, slack
):
    _tenant, owner, anna, app = await _seed(app_session_factory)
    old = slack.add(anna.email, active=False)
    await _connect(client, owner, app)
    await _grant(client, owner, app, [anna.id])
    await _drain(app_session_factory)
    assert list(slack.users) == [old]
    assert slack.users[old]["active"] is True


async def test_everyone_policy_creates_accounts_on_connect(app_session_factory, client, slack):
    _tenant, owner, anna, app = await _seed(app_session_factory)
    patched = await client.patch(
        f"/apps/{app.id}", json={"access_policy": "everyone"}, cookies=_cookie(owner)
    )
    assert patched.status_code == 200
    # The owner already has a Slack account made by hand: we link it, not duplicate it.
    slack.add(owner.email)
    await _connect(client, owner, app)
    await _drain(app_session_factory)
    assert {u["emails"][0]["value"] for u in slack.users.values()} == {owner.email, anna.email}
    assert all(u["active"] for u in slack.users.values())

    # Admins only: Anna's account is deactivated, the owner's stays.
    await client.patch(f"/apps/{app.id}", json={"access_policy": "admins"}, cookies=_cookie(owner))
    await _drain(app_session_factory)
    assert slack.by_email(anna.email)["active"] is False
    assert slack.by_email(owner.email)["active"] is True


async def test_people_without_access_are_left_alone(app_session_factory, client, slack):
    _tenant, owner, anna, app = await _seed(app_session_factory)
    slack.add(anna.email)  # made in Slack by hand, never given access through us
    await _connect(client, owner, app)
    await client.patch(f"/users/{anna.id}", json={"disabled": True}, cookies=_cookie(owner))
    await _drain(app_session_factory)
    assert slack.by_email(anna.email)["active"] is True


async def test_pending_email_grant_creates_then_removal_deactivates(
    app_session_factory, client, slack
):
    tenant, owner, _anna, app = await _seed(app_session_factory)
    await _connect(client, owner, app)
    new_hire = f"ola@{tenant.workspace_domain}"
    await _grant(client, owner, app, [], [new_hire])
    await _drain(app_session_factory)
    assert slack.by_email(new_hire)["active"] is True

    await _grant(client, owner, app, [], [])
    await _drain(app_session_factory)
    assert slack.by_email(new_hire)["active"] is False
    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        rows = (
            await session.scalars(select(AppAccount).where(AppAccount.client_pk == app.id))
        ).all()
    assert rows == []


async def test_deleting_a_person_deactivates_without_keeping_their_address(
    app_session_factory, client, slack
):
    tenant, owner, anna, app = await _seed(app_session_factory)
    await _connect(client, owner, app)
    await _grant(client, owner, app, [anna.id])
    await _drain(app_session_factory)

    deleted = await client.delete(f"/users/{anna.id}", cookies=_cookie(owner))
    assert deleted.status_code == 204
    await _drain(app_session_factory)
    assert slack.by_email(anna.email)["active"] is False
    last = (await _events(app_session_factory, tenant))[-1]
    assert last.details["action"] == "deactivated"
    assert last.email == ""
    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        assert (
            await session.scalars(select(AppAccount).where(AppAccount.client_pk == app.id))
        ).all() == []


async def test_busy_slack_is_retried_later(app_session_factory, client, slack):
    tenant, owner, anna, app = await _seed(app_session_factory)
    await _connect(client, owner, app)
    slack.busy = 1
    await _grant(client, owner, app, [anna.id])
    await _drain(app_session_factory)
    assert slack.by_email(anna.email) is None

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        account = await session.scalar(select(AppAccount).where(AppAccount.client_pk == app.id))
        outbox = await session.get(ProvisionOutbox, account.id)
        assert account.attempts == 1
        assert account.last_error == "provision_rate_limited"
        assert outbox.next_attempt_at > datetime.now(UTC)
        outbox.next_attempt_at = datetime.now(UTC)
        await session.commit()

    await _drain(app_session_factory)
    assert slack.by_email(anna.email)["active"] is True


async def test_a_rejected_token_fails_and_is_audited(app_session_factory, client, slack):
    tenant, owner, anna, app = await _seed(app_session_factory)
    await _connect(client, owner, app)
    monkey_token = "xoxp-revoked"
    from app.agents.secrets import encrypt_secret

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        row = await session.get(OAuthClient, app.id)
        row.provision_secret = encrypt_secret(monkey_token)
        await session.commit()

    await _grant(client, owner, app, [anna.id])
    await _drain(app_session_factory)
    accounts = (await client.get(f"/apps/{app.id}/accounts", cookies=_cookie(owner))).json()
    (row,) = accounts["accounts"]
    assert row["status"] == "failed"
    assert row["last_error"] == "provision_key_rejected"
    (event,) = await _events(app_session_factory, tenant)
    assert event.details["action"] == "failed"
    assert event.error_code == "provision_key_rejected"


async def test_username_taken_gets_a_number(app_session_factory, client, slack):
    _tenant, owner, anna, app = await _seed(app_session_factory)
    slack.add("someone@else.no", username="anna.berg")
    await _connect(client, owner, app)
    await _grant(client, owner, app, [anna.id])
    await _drain(app_session_factory)
    assert slack.by_email(anna.email)["userName"] == "anna.berg2"


async def test_slack_usernames():
    assert scim.slack_username("Anna.Berg+test@firma.no") == "anna.bergtest"
    assert scim.slack_username("ø@firma.no") == "user"
    assert len(scim.slack_username("a" * 40 + "@x.no", 1)) == 21


async def test_first_sign_in_creates_the_account(app_session_factory, client, slack):
    from app.auth.identity import upsert_user_from_oidc

    tenant, owner, _anna, app = await _seed(app_session_factory)
    await client.patch(f"/apps/{app.id}", json={"access_policy": "everyone"}, cookies=_cookie(owner))
    await _connect(client, owner, app)
    await _drain(app_session_factory)
    newcomer = f"kari@{tenant.workspace_domain}"
    async with app_session_factory() as session:
        await upsert_user_from_oidc(
            session,
            email=newcomer,
            idp=IdentityProvider.google,
            oidc_sub=f"kari-{uuid4().hex[:6]}",
            display_name="Kari Nordmann",
            hosted_domain=tenant.workspace_domain,
        )
        await session.commit()
    await _drain(app_session_factory)
    assert slack.by_email(newcomer)["displayName"] == "Kari Nordmann"
