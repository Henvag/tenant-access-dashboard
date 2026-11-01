"""Audit CSV export, outbound webhooks and DNS-verified company domains."""

import base64
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from itsdangerous import TimestampSigner
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import dns_check, main
from app.api.audit import csv_safe
from app.auth.identity import LoginError, is_managed_account, upsert_user_from_oidc
from app.auth.rls import set_tenant_rls
from app.config import settings
from app.db import get_db
from app.models import (
    IdentityProvider,
    Tenant,
    User,
    UserRole,
    WebhookDelivery,
    WebhookOutbox,
)
from app.webhooks import service, worker
from app.webhooks.signing import new_secret, sign, verify

pytestmark = pytest.mark.asyncio


def _cookie(user: User) -> dict[str, str]:
    payload = {"user_id": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role.value}
    data = base64.b64encode(json.dumps(payload).encode())
    return {"session": TimestampSigner(settings.session_secret).sign(data).decode()}


async def _seed(factory: async_sessionmaker[AsyncSession], prefix: str = "hooks") -> tuple[Tenant, User]:
    suffix = uuid4().hex[:8]
    domain = f"{prefix}-{suffix}.com"
    async with factory() as session:
        tenant = Tenant(name=f"Co {suffix}", workspace_domain=domain)
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
        session.add(owner)
        await session.flush()
        row = await session.get(Tenant, tenant.id)
        row.owner_user_id = owner.id
        await session.refresh(owner)
        await session.commit()
    return tenant, owner


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


# --- signing ---------------------------------------------------------------


def test_signature_matches_standard_webhooks_reference() -> None:
    # Test vector from the Standard Webhooks spec.
    secret = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
    body = b'{"test": 2432232314}'
    signature = sign(secret, "msg_p5jXN8AQM9LWM0D4loKWxJek", 1614265330, body)
    assert signature == "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE="
    assert verify(secret, "msg_p5jXN8AQM9LWM0D4loKWxJek", 1614265330, body, signature)
    assert not verify(secret, "msg_other", 1614265330, body, signature)


def test_new_secret_has_prefix_and_32_bytes() -> None:
    secret = new_secret()
    assert secret.startswith("whsec_")
    assert len(base64.b64decode(secret[6:])) == 32


@pytest.mark.parametrize(
    "url,code",
    [
        ("http://example.com/hook", "https_url_required"),
        ("https://localhost/hook", "webhook_url_private"),
        ("https://127.0.0.1/hook", "webhook_url_private"),
        ("https://10.1.2.3/hook", "webhook_url_private"),
        ("https://169.254.169.254/latest", "webhook_url_private"),
        ("https://user:pw@example.com/", "webhook_url_invalid"),
    ],
)
def test_webhook_url_must_be_public_https(url: str, code: str) -> None:
    with pytest.raises(service.WebhookUrlError) as err:
        service.validate_url_shape(url)
    assert str(err.value) == code


def test_csv_cells_cannot_become_formulas() -> None:
    assert csv_safe("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert csv_safe("@SUM(1)") == "'@SUM(1)"
    assert csv_safe("ada@example.com") == "ada@example.com"
    assert csv_safe(None) == ""


# --- webhooks ----------------------------------------------------------------


async def test_audit_event_queues_signed_delivery_and_worker_sends_it(
    client: AsyncClient,
    app_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant, owner = await _seed(app_session_factory)
    cookie = _cookie(owner)

    created = await client.post(
        "/webhooks",
        json={"url": "https://hooks.example.com/in", "event_types": ["domain_added"]},
        cookies=cookie,
    )
    assert created.status_code == 201, created.text
    secret = created.json()["secret"]
    assert created.json()["secret_hint"] == secret[-4:]
    listed = await client.get("/webhooks", cookies=cookie)
    assert "secret" not in listed.json()["endpoints"][0]

    # domain_added is subscribed; webhook_created (the event above) was not.
    added = await client.post("/company/domains", json={"domain": "acme-extra.example"}, cookies=cookie)
    assert added.status_code == 201, added.text

    sent: list[tuple[str, dict, bytes]] = []

    async def fake_post(url, headers, body):
        sent.append((url, headers, body))
        import httpx

        return httpx.Response(204)

    async def public(url):
        return None

    monkeypatch.setattr(service, "_post", fake_post)
    monkeypatch.setattr(service, "assert_public_host", public)

    # Only rows due for this tenant matter; other tests may leave rows behind.
    async with app_session_factory() as session:
        await session.execute(
            update(WebhookOutbox)
            .where(WebhookOutbox.tenant_id != tenant.id)
            .values(next_attempt_at=datetime.now(UTC) + timedelta(days=1))
        )
        await session.commit()
    await worker.run_once(app_session_factory)

    assert len(sent) == 1
    url, headers, body = sent[0]
    assert url == "https://hooks.example.com/in"
    payload = json.loads(body)
    assert payload["type"] == "domain_added"
    assert payload["data"]["details"] == {"domain": "acme-extra.example"}
    assert verify(
        secret, headers["webhook-id"], int(headers["webhook-timestamp"]), body, headers["webhook-signature"]
    )

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        deliveries = (await session.scalars(select(WebhookDelivery))).all()
        assert [(d.status, d.attempts, d.response_status) for d in deliveries] == [("succeeded", 1, 204)]
        assert (await session.scalars(select(WebhookOutbox).where(WebhookOutbox.tenant_id == tenant.id))).all() == []


async def test_failed_delivery_is_rescheduled_then_given_up(
    client: AsyncClient,
    app_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant, owner = await _seed(app_session_factory)
    cookie = _cookie(owner)
    await client.post("/webhooks", json={"url": "https://down.example.com/"}, cookies=cookie)
    # All events: the webhook_created row itself is queued.
    async def fake_post(url, headers, body):
        import httpx

        return httpx.Response(500)

    async def public(url):
        return None

    monkeypatch.setattr(service, "_post", fake_post)
    monkeypatch.setattr(service, "assert_public_host", public)

    async with app_session_factory() as session:
        await session.execute(
            update(WebhookOutbox)
            .where(WebhookOutbox.tenant_id != tenant.id)
            .values(next_attempt_at=datetime.now(UTC) + timedelta(days=1))
        )
        await session.commit()
    await worker.run_once(app_session_factory)

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        delivery = (await session.scalars(select(WebhookDelivery))).one()
        assert (delivery.status, delivery.attempts, delivery.last_error) == ("pending", 1, "HTTP 500")
        outbox = await session.get(WebhookOutbox, delivery.id)
        assert outbox.next_attempt_at > datetime.now(UTC) + timedelta(seconds=20)

    assert service.next_attempt_after(service.MAX_ATTEMPTS) is None


async def test_webhooks_are_invisible_to_other_tenants(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, owner_a = await _seed(app_session_factory, "hook-a")
    _, owner_b = await _seed(app_session_factory, "hook-b")
    created = await client.post("/webhooks", json={"url": "https://a.example.com/"}, cookies=_cookie(owner_a))
    endpoint_id = created.json()["id"]

    other = await client.get("/webhooks", cookies=_cookie(owner_b))
    assert other.json()["endpoints"] == []
    gone = await client.delete(f"/webhooks/{endpoint_id}", cookies=_cookie(owner_b))
    assert gone.status_code == 404
    deliveries = await client.get(f"/webhooks/{endpoint_id}/deliveries", cookies=_cookie(owner_b))
    assert deliveries.status_code == 404


async def test_webhook_limit_and_unknown_events(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, owner = await _seed(app_session_factory)
    cookie = _cookie(owner)
    bad = await client.post("/webhooks", json={"url": "https://x.example.com/", "event_types": ["nope"]}, cookies=cookie)
    assert bad.json()["detail"] == "webhook_event_unknown"
    for n in range(service.MAX_ENDPOINTS):
        ok = await client.post("/webhooks", json={"url": f"https://x{n}.example.com/"}, cookies=cookie)
        assert ok.status_code == 201
    full = await client.post("/webhooks", json={"url": "https://y.example.com/"}, cookies=cookie)
    assert full.json()["detail"] == "webhook_limit_reached"


# --- audit export ------------------------------------------------------------


async def test_audit_export_is_csv_for_own_tenant_and_is_audited(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, owner_a = await _seed(app_session_factory, "exp-a")
    _, owner_b = await _seed(app_session_factory, "exp-b")
    await client.post("/company/domains", json={"domain": "a-only.example"}, cookies=_cookie(owner_a))

    first = await client.get("/audit/export.csv", cookies=_cookie(owner_a))
    assert first.status_code == 200
    assert first.headers["content-type"].startswith("text/csv")
    assert "attachment" in first.headers["content-disposition"]
    lines = first.text.strip().splitlines()
    assert lines[0] == "created_at,event_type,email,display_name,idp,error_code,ip_address,details"
    assert any("domain_added" in line for line in lines[1:])

    other = await client.get("/audit/export.csv", cookies=_cookie(owner_b))
    assert "a-only.example" not in other.text

    events = await client.get("/audit", cookies=_cookie(owner_a))
    assert events.json()[0]["event_type"] == "audit_exported"


# --- domains -----------------------------------------------------------------


async def test_verified_domain_lets_its_people_join_the_company(
    client: AsyncClient,
    app_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant, owner = await _seed(app_session_factory, "dns")
    cookie = _cookie(owner)
    extra = f"extra-{uuid4().hex[:8]}.com"

    added = await client.post("/company/domains", json={"domain": extra.upper()}, cookies=cookie)
    assert added.status_code == 201
    body = added.json()
    assert body["domain"] == extra and body["verified"] is False
    assert body["record_name"] == f"_tenant-access.{extra}"

    async with app_session_factory() as session:
        with pytest.raises(LoginError) as before:
            await upsert_user_from_oidc(
                session, email=f"kari@{extra}", idp=IdentityProvider.google,
                oidc_sub=f"kari-{extra}", display_name="Kari", hosted_domain=extra,
            )
        assert before.value.code == "no_tenant"

    async def missing(name):
        return ["v=spf1 -all"]

    monkeypatch.setattr(dns_check, "txt_records", missing)
    nope = await client.post(f"/company/domains/{body['id']}/verify", cookies=cookie)
    assert nope.status_code == 422 and nope.json()["detail"] == "dns_record_missing"

    async def present(name):
        assert name == body["record_name"]
        return ["v=spf1 -all", body["record_value"]]

    monkeypatch.setattr(dns_check, "txt_records", present)
    ok = await client.post(f"/company/domains/{body['id']}/verify", cookies=cookie)
    assert ok.status_code == 200 and ok.json()["verified"] is True

    async with app_session_factory() as session:
        user = await upsert_user_from_oidc(
            session, email=f"kari@{extra}", idp=IdentityProvider.google,
            oidc_sub=f"kari-{extra}", display_name="Kari", hosted_domain=extra,
        )
        assert user.tenant_id == tenant.id and user.role == UserRole.user
        await session.rollback()

    # Another company can neither add nor register on it now.
    _, rival = await _seed(app_session_factory, "rival")
    taken = await client.post("/company/domains", json={"domain": extra}, cookies=_cookie(rival))
    assert taken.status_code == 409 and taken.json()["detail"] == "domain_taken"


async def test_domain_rules(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    tenant, owner = await _seed(app_session_factory, "rules")
    _, other = await _seed(app_session_factory, "rules-other")
    cookie = _cookie(owner)
    assert (await client.post("/company/domains", json={"domain": "gmail.com"}, cookies=cookie)).json()["detail"] == "domain_consumer"
    assert (await client.post("/company/domains", json={"domain": tenant.workspace_domain}, cookies=cookie)).json()["detail"] == "domain_exists"
    assert (await client.post("/company/domains", json={"domain": other.email.split("@")[1]}, cookies=cookie)).json()["detail"] == "domain_taken"

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        member = User(
            tenant_id=tenant.id, email=f"m@{tenant.workspace_domain}", idp=IdentityProvider.google,
            oidc_sub=f"m-{uuid4().hex}", role=UserRole.admin,
        )
        session.add(member)
        await session.flush()
        await session.refresh(member)
        await session.commit()
    not_owner = await client.post("/company/domains", json={"domain": "x-co.example"}, cookies=_cookie(member))
    assert not_owner.status_code == 403
    assert (await client.get("/company/domains", cookies=_cookie(member))).status_code == 200


async def test_require_managed_accounts_refuses_personal_google_accounts(
    client: AsyncClient, app_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    tenant, owner = await _seed(app_session_factory, "managed")
    domain = tenant.workspace_domain
    on = await client.put("/company/sign-in-policy", json={"require_managed_accounts": True}, cookies=_cookie(owner))
    assert on.status_code == 200 and on.json()["require_managed_accounts"] is True

    async with app_session_factory() as session:
        with pytest.raises(LoginError) as refused:
            await upsert_user_from_oidc(
                session, email=f"p@{domain}", idp=IdentityProvider.google, oidc_sub="personal-1",
                display_name=None, hosted_domain=None,
                managed_account=is_managed_account(IdentityProvider.google, {}),
            )
        assert refused.value.code == "managed_account_required"

    async with app_session_factory() as session:
        user = await upsert_user_from_oidc(
            session, email=f"w@{domain}", idp=IdentityProvider.google, oidc_sub=f"ws-{domain}",
            display_name=None, hosted_domain=domain,
            managed_account=is_managed_account(IdentityProvider.google, {"hd": domain}),
        )
        assert user.tenant_id == tenant.id
        await session.rollback()


def test_managed_account_detection() -> None:
    assert is_managed_account(IdentityProvider.google, {"hd": "acme.com"})
    assert not is_managed_account(IdentityProvider.google, {})
    assert is_managed_account(IdentityProvider.microsoft, {"tid": "1234"})
    assert not is_managed_account(
        IdentityProvider.microsoft, {"tid": "9188040d-6c67-4c5b-b112-36a304b66dad"}
    )
