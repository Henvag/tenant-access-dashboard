"""SAML identity provider: registration, metadata, SP- and IdP-initiated sign-in.

Responses are checked by python3-saml (OneLogin's service-provider toolkit,
built on xmlsec), standing in for Slack: it verifies signatures, audience,
destination, recipient, timing and InResponseTo the way a real app does.
"""

import base64
import json
import re
from datetime import UTC, datetime
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest
from httpx import AsyncClient
from itsdangerous import TimestampSigner
from onelogin.saml2.authn_request import OneLogin_Saml2_Authn_Request
from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser
from onelogin.saml2.response import OneLogin_Saml2_Response
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from onelogin.saml2.utils import OneLogin_Saml2_Utils
from sqlalchemy import select

from app.auth.rls import set_tenant_rls
from app.config import settings
from app.models import AuditEvent, AuditEventType, User
from app.saml import certs
from app.saml.messages import encode_redirect
from tests.test_oidc_provider import _seed, _session_cookie, client  # noqa: F401

pytestmark = pytest.mark.asyncio

SP_ENTITY = "https://slack.com"
ACS = "https://acme.slack.com/sso/saml"


@pytest.fixture(autouse=True)
def _fresh_cert():
    certs.reset_cache()
    yield
    certs.reset_cache()


def _cookie(user: User, **extra) -> str:
    payload = {"user_id": str(user.id), "tenant_id": str(user.tenant_id), "role": user.role.value}
    payload.update(extra)
    data = base64.b64encode(json.dumps(payload).encode())
    return TimestampSigner(settings.session_secret).sign(data).decode()


async def _register(http: AsyncClient, admin: User, **overrides) -> dict:
    body = {
        "name": "Slack",
        "protocol": "saml",
        "saml_entity_id": SP_ENTITY,
        "saml_acs_url": ACS,
        "saml_nameid": "persistent",
        "launch_url": "https://acme.slack.com",
        "access_policy": "assigned",
    }
    body.update(overrides)
    response = await http.post("/apps", json=body, cookies={"session": _session_cookie(admin)})
    assert response.status_code == 201, response.text
    return response.json()


async def _sp_settings(http: AsyncClient, app: dict) -> OneLogin_Saml2_Settings:
    meta = await http.get(urlsplit(app["saml_metadata_url"]).path)
    assert meta.status_code == 200
    idp = OneLogin_Saml2_IdPMetadataParser.parse(meta.text)
    data = {
        "strict": True,
        "sp": {
            "entityId": SP_ENTITY,
            "assertionConsumerService": {"url": ACS},
            "NameIDFormat": "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent",
        },
        "security": {"wantAssertionsSigned": True, "wantMessagesSigned": True},
        "idp": idp["idp"],
    }
    return OneLogin_Saml2_Settings(data, sp_validation_only=True)


def _authn_request(sp: OneLogin_Saml2_Settings) -> tuple[str, str]:
    request = OneLogin_Saml2_Authn_Request(sp)
    return request.get_id(), request.get_xml()


def _form_fields(html: str) -> dict[str, str]:
    action = re.search(r'<form method="post" action="([^"]+)"', html)
    fields = dict(re.findall(r'name="(\w+)" value="([^"]*)"', html))
    return {"action": unescape(action.group(1)) if action else "", **{k: unescape(v) for k, v in fields.items()}}


def _sp_accepts(sp: OneLogin_Saml2_Settings, saml_response: str, request_id: str | None):
    response = OneLogin_Saml2_Response(sp, saml_response)
    request_data = {
        "https": "on",
        "http_host": "acme.slack.com",
        "script_name": "/sso/saml",
        "post_data": {"SAMLResponse": saml_response},
    }
    ok = response.is_valid(request_data, request_id, raise_exceptions=True)
    assert ok, response.get_error()
    return response


async def _grant(http: AsyncClient, admin: User, app_id: str, user: User) -> None:
    response = await http.put(
        f"/apps/{app_id}/grants",
        json={"user_ids": [str(user.id)]},
        cookies={"session": _session_cookie(admin)},
    )
    assert response.status_code == 200, response.text


def _query(location: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(location).query).items()}


async def test_register_and_metadata(client: AsyncClient, app_session_factory):
    _, admin, _ = await _seed(app_session_factory)
    app = await _register(client, admin)
    assert app["protocol"] == "saml"
    assert app["redirect_uris"] == []
    assert app["saml_sso_url"].endswith(f"/saml/{app['client_id']}/sso")
    assert app["saml_issuer"] == app["saml_metadata_url"]

    meta = await client.get(urlsplit(app["saml_metadata_url"]).path)
    assert meta.headers["content-type"].startswith("application/samlmetadata+xml")
    assert "X509Certificate" in meta.text and app["saml_sso_url"] in meta.text

    pem = await client.get(urlsplit(app["saml_certificate_url"]).path)
    assert pem.text.startswith("-----BEGIN CERTIFICATE-----")

    # OpenID Connect endpoints refuse a SAML app.
    authorize = await client.get(
        "/oauth/authorize",
        params={"client_id": app["client_id"], "redirect_uri": ACS, "response_type": "code"},
        cookies={"session": _session_cookie(admin)},
    )
    assert "app_invalid_redirect" in authorize.headers["location"]


async def test_create_validation(client: AsyncClient, app_session_factory):
    _, admin, _ = await _seed(app_session_factory)
    cookies = {"session": _session_cookie(admin)}
    missing = await client.post(
        "/apps", json={"name": "X", "protocol": "saml", "saml_entity_id": SP_ENTITY}, cookies=cookies
    )
    assert missing.status_code == 422
    plain_http = await client.post(
        "/apps",
        json={
            "name": "X",
            "protocol": "saml",
            "saml_entity_id": SP_ENTITY,
            "saml_acs_url": "http://acme.example.com/acs",
        },
        cookies=cookies,
    )
    assert plain_http.status_code == 422
    oidc_with_saml = await client.post(
        "/apps", json={"name": "X", "saml_acs_url": ACS, "redirect_uris": [ACS]}, cookies=cookies
    )
    assert oidc_with_saml.status_code == 422


async def test_sp_initiated_signin_checks_access(client: AsyncClient, app_session_factory):
    tenant, admin, member = await _seed(app_session_factory)
    app = await _register(client, admin)
    sp = await _sp_settings(client, app)
    sso = urlsplit(app["saml_sso_url"]).path

    # Not granted yet: denied and audited.
    request_id, xml = _authn_request(sp)
    denied = await client.get(
        sso,
        params={"SAMLRequest": encode_redirect(xml.encode()), "RelayState": "r1"},
        cookies={"session": _session_cookie(member)},
    )
    assert denied.status_code == 302
    assert _query(denied.headers["location"]) == {
        "error": "app_access_denied",
        "app": "Slack",
        "reason": "not_assigned",
    }

    await _grant(client, admin, app["id"], member)
    request_id, xml = _authn_request(sp)
    ok = await client.get(
        sso,
        params={"SAMLRequest": encode_redirect(xml.encode()), "RelayState": "r2"},
        cookies={"session": _session_cookie(member)},
    )
    assert ok.status_code == 200, ok.text
    form = _form_fields(ok.text)
    assert form["action"] == ACS
    assert form["RelayState"] == "r2"
    response = _sp_accepts(sp, form["SAMLResponse"], request_id)
    assert response.get_nameid() == str(member.id)
    attrs = response.get_attributes()
    assert attrs["User.Email"] == [member.email]
    assert attrs["first_name"] == ["Mia"] and attrs["last_name"] == ["Member"]
    assert attrs["role"] == ["member"]

    # The response is for this request only.
    with pytest.raises(Exception):
        _sp_accepts(sp, form["SAMLResponse"], "_some_other_request")

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        events = (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.tenant_id == tenant.id)
            )
        ).all()
    kinds = [(e.event_type, (e.details or {}).get("protocol")) for e in events]
    assert (AuditEventType.app_login_denied, "saml") in kinds
    assert (AuditEventType.app_login, "saml") in kinds


async def test_post_binding_redirects_without_touching_session(
    client: AsyncClient, app_session_factory
):
    _, admin, _ = await _seed(app_session_factory)
    app = await _register(client, admin, access_policy="everyone")
    sp = await _sp_settings(client, app)
    _, xml = _authn_request(sp)
    posted = await client.post(
        urlsplit(app["saml_sso_url"]).path,
        data={"SAMLRequest": base64.b64encode(xml.encode()).decode(), "RelayState": "abc"},
    )
    assert posted.status_code == 303
    assert "set-cookie" not in posted.headers
    location = posted.headers["location"]
    assert urlsplit(location).path == urlsplit(app["saml_sso_url"]).path
    assert _query(location)["RelayState"] == "abc"

    # Following it as the signed-in admin completes sign-in.
    done = await client.get(
        urlsplit(location).path + "?" + urlsplit(location).query,
        cookies={"session": _session_cookie(admin)},
    )
    assert done.status_code == 200
    _sp_accepts(sp, _form_fields(done.text)["SAMLResponse"], None)


async def test_parks_until_signed_in(client: AsyncClient, app_session_factory):
    _, admin, _ = await _seed(app_session_factory)
    app = await _register(client, admin, access_policy="everyone")
    sp = await _sp_settings(client, app)
    request_id, xml = _authn_request(sp)
    parked = await client.get(
        urlsplit(app["saml_sso_url"]).path,
        params={"SAMLRequest": encode_redirect(xml.encode()), "RelayState": "keep"},
    )
    assert parked.status_code == 302
    assert _query(parked.headers["location"]) == {"continue": "Slack"}
    assert "pending_saml" in base64.b64decode(
        parked.cookies["session"].split(".")[0] + "=="
    ).decode()

    # After sign-in, /oauth/resume (what the SPA calls) points to /saml/continue.
    pending = {"c": app["client_id"], "r": request_id, "s": "keep"}
    cookie = {"session": _cookie(admin, pending_saml=pending)}
    resume = await client.get("/oauth/resume", cookies=cookie)
    assert resume.headers["location"].endswith("/saml/continue")
    done = await client.get("/saml/continue", cookies=cookie)
    assert done.status_code == 200
    form = _form_fields(done.text)
    assert form["RelayState"] == "keep"
    _sp_accepts(sp, form["SAMLResponse"], request_id)


async def test_disabled_person_and_wrong_requests(client: AsyncClient, app_session_factory):
    tenant, admin, member = await _seed(app_session_factory)
    app = await _register(client, admin, access_policy="everyone")
    sp = await _sp_settings(client, app)
    sso = urlsplit(app["saml_sso_url"]).path

    # An ACS URL that was not registered is refused before anything else.
    _, xml = _authn_request(sp)
    tampered = xml.replace(ACS, "https://evil.example.com/acs")
    wrong = await client.get(
        sso,
        params={"SAMLRequest": encode_redirect(tampered.encode())},
        cookies={"session": _session_cookie(member)},
    )
    assert _query(wrong.headers["location"])["error"] == "saml_wrong_acs"

    garbage = await client.get(sso, params={"SAMLRequest": "not-saml"})
    assert _query(garbage.headers["location"])["error"] == "saml_bad_request"

    async with app_session_factory() as session:
        await set_tenant_rls(session, tenant.id)
        row = await session.scalar(select(User).where(User.id == member.id))
        row.disabled_at = datetime.now(UTC)
        await session.commit()
    _, xml = _authn_request(sp)
    disabled = await client.get(
        sso,
        params={"SAMLRequest": encode_redirect(xml.encode())},
        cookies={"session": _session_cookie(member)},
    )
    assert _query(disabled.headers["location"])["reason"] == "user_disabled"


async def test_idp_initiated_launch_and_email_nameid(client: AsyncClient, app_session_factory):
    _, admin, member = await _seed(app_session_factory)
    app = await _register(
        client, admin, access_policy="everyone", saml_nameid="email", launch_url=None
    )
    sp = await _sp_settings(client, app)
    mine = await client.get("/apps/mine", cookies={"session": _session_cookie(member)})
    tile = next(a for a in mine.json() if a["id"] == app["id"])
    assert tile["protocol"] == "saml"
    launch = tile["launch_url"]
    assert launch == f"/saml/{app['client_id']}/launch"

    opened = await client.get(launch, cookies={"session": _session_cookie(member)})
    assert opened.status_code == 200
    response = _sp_accepts(sp, _form_fields(opened.text)["SAMLResponse"], None)
    assert response.get_nameid() == member.email
    assert "InResponseTo" not in OneLogin_Saml2_Utils.b64decode(
        _form_fields(opened.text)["SAMLResponse"]
    ).decode()


async def test_patch_saml_fields(client: AsyncClient, app_session_factory):
    _, admin, _ = await _seed(app_session_factory)
    cookies = {"session": _session_cookie(admin)}
    app = await _register(client, admin)
    patched = await client.patch(
        f"/apps/{app['id']}",
        json={"saml_acs_url": "https://other.slack.com/sso/saml"},
        cookies=cookies,
    )
    assert patched.status_code == 200
    assert patched.json()["saml_acs_url"] == "https://other.slack.com/sso/saml"
    redirects = await client.patch(
        f"/apps/{app['id']}", json={"redirect_uris": [ACS]}, cookies=cookies
    )
    assert redirects.json()["detail"] == "saml_no_redirects"
