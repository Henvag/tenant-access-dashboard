"""SAML 2.0 identity provider endpoints, for cloud apps such as Slack and Zoom.

Flow (service-provider initiated):
  1. The app sends the browser to /saml/{client_id}/sso with an AuthnRequest,
     by redirect (GET) or by an auto-posted form (POST).
  2. If the person has no dashboard session we park the request in the session
     and send them to the landing page; /auth/callback resumes it at
     /saml/continue after Google/Microsoft sign-in.
  3. We run the same checks as OpenID Connect sign-in (company, disabled
     people, the app's access policy and grants) and audit the decision.
  4. On success we post a signed Response to the app's registered ACS URL.

/saml/{client_id}/launch starts the same flow from the dashboard without a
request (identity-provider initiated).
"""

from __future__ import annotations

import base64
import html
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.oauth import _frontend, _resolve_client
from app.auth.audit import record_app_event
from app.auth.identity import read_login_session
from app.config import settings
from app.db import get_db
from app.models import AuditEventType, IdentityProvider, OAuthClient, Tenant, User
from app.oauth.pending import PENDING_AUTHORIZE_KEY, PENDING_SAML_KEY
from app.oauth.service import access_denial_reason, role_claim
from app.saml import certs
from app.saml.messages import (
    BINDING_POST,
    NAMEID_FORMATS,
    SamlError,
    build_response,
    decode_request,
    encode_redirect,
    idp_metadata,
    parse_authn_request,
    split_name,
)

router = APIRouter(prefix="/saml", tags=["saml-provider"])

_MAX_RELAY_STATE = 1024


def entity_id(client_id: str) -> str:
    return f"{settings.public_origin}/saml/{client_id}/metadata"


def sso_url(client_id: str) -> str:
    return f"{settings.public_origin}/saml/{client_id}/sso"


async def _saml_client(db: AsyncSession, client_id: str) -> OAuthClient | None:
    client = await _resolve_client(db, client_id)
    if client is None or not client.is_saml:
        return None
    return client


@router.get("/{client_id}/metadata")
async def metadata(client_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    cert = await certs.signing_cert(db)
    if await _saml_client(db, client_id) is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    body = idp_metadata(cert=cert, entity_id=entity_id(client_id), sso_url=sso_url(client_id))
    return Response(body, media_type="application/samlmetadata+xml")


@router.get("/{client_id}/certificate.pem")
async def certificate(client_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    cert = await certs.signing_cert(db)
    if await _saml_client(db, client_id) is None:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return Response(
        cert.certificate_pem,
        media_type="application/x-pem-file",
        headers={"Content-Disposition": 'attachment; filename="tenant-access-saml.pem"'},
    )


@router.post("/{client_id}/sso")
async def sso_post(
    client_id: str,
    SAMLRequest: str = Form(""),  # noqa: N803 - SAML binding field names
    RelayState: str = Form(""),  # noqa: N803
):
    """HTTP-POST binding. Re-sent as a redirect so the browser includes our cookie.

    The app's form post is cross-site, so the Lax session cookie is not sent with
    it; a top-level GET is. Nothing here reads or writes the session.
    """
    try:
        xml = decode_request(SAMLRequest, deflated=False)
        parse_authn_request(xml)
    except SamlError as exc:
        return _frontend({"error": exc.code})
    params = {"SAMLRequest": encode_redirect(xml)}
    if RelayState:
        params["RelayState"] = RelayState[:_MAX_RELAY_STATE]
    return RedirectResponse(
        f"{settings.public_origin}/saml/{client_id}/sso?{urlencode(params)}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/{client_id}/sso")
async def sso_redirect(client_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """HTTP-Redirect binding: SAMLRequest is DEFLATE + base64 in the query."""
    cert = await certs.signing_cert(db)
    client = await _saml_client(db, client_id)
    if client is None:
        return _frontend({"error": "app_unknown_client"})
    q = request.query_params
    try:
        authn = parse_authn_request(decode_request(q.get("SAMLRequest", ""), deflated=True))
    except SamlError as exc:
        return _frontend({"error": exc.code, "app": client.name})
    if authn.issuer and authn.issuer != client.saml_entity_id:
        return _frontend({"error": "saml_wrong_app", "app": client.name})
    if authn.acs_url and authn.acs_url != client.saml_acs_url:
        # Never post to a URL that was not registered.
        return _frontend({"error": "saml_wrong_acs", "app": client.name})
    if authn.protocol_binding and authn.protocol_binding != BINDING_POST:
        return _frontend({"error": "saml_bad_request", "app": client.name})
    pending = {
        "c": client.client_id,
        "r": authn.id,
        "s": (q.get("RelayState") or "")[:_MAX_RELAY_STATE],
    }
    return await _complete(request, db, client, cert, pending)


@router.get("/{client_id}/launch")
async def launch(client_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Open the app from the dashboard: an unsolicited (IdP-initiated) response."""
    cert = await certs.signing_cert(db)
    client = await _saml_client(db, client_id)
    if client is None:
        return _frontend({"error": "app_unknown_client"})
    return await _complete(request, db, client, cert, {"c": client.client_id, "r": None, "s": ""})


@router.get("/continue")
async def resume(request: Request, db: AsyncSession = Depends(get_db)):
    """Finish a parked SAML sign-in once the person has signed in to us."""
    pending = request.session.get(PENDING_SAML_KEY)
    if not isinstance(pending, dict) or not pending.get("c"):
        request.session.pop(PENDING_SAML_KEY, None)
        return _frontend({})
    cert = await certs.signing_cert(db)
    client = await _saml_client(db, str(pending["c"]))
    if client is None:
        request.session.pop(PENDING_SAML_KEY, None)
        return _frontend({"error": "app_unknown_client"})
    return await _complete(request, db, client, cert, pending)


def _park(request: Request, client: OAuthClient, pending: dict) -> RedirectResponse:
    request.session.pop(PENDING_AUTHORIZE_KEY, None)
    request.session[PENDING_SAML_KEY] = pending
    return _frontend({"continue": client.name})


async def _deny(
    request: Request, db: AsyncSession, client: OAuthClient, reason: str, user: User | None
) -> RedirectResponse:
    request.session.pop(PENDING_SAML_KEY, None)
    await record_app_event(
        db,
        tenant_id=client.tenant_id,
        event_type=AuditEventType.app_login_denied,
        email=user.email if user else "unknown@other-tenant",
        user_id=user.id if user else None,
        idp=user.idp if user else IdentityProvider.google,
        request=request,
        error_code=reason,
        details={"app": client.name, "reason": reason, "protocol": "saml"},
    )
    await db.commit()
    return _frontend({"error": "app_access_denied", "app": client.name, "reason": reason})


async def _complete(
    request: Request,
    db: AsyncSession,
    client: OAuthClient,
    cert: certs.SigningCert,
    pending: dict,
):
    identities = read_login_session(request.session)
    if identities is None:
        return _park(request, client, pending)
    session_user_id, session_tenant_id = identities
    if session_tenant_id != client.tenant_id:
        return await _deny(request, db, client, "wrong_tenant", None)
    user = await db.scalar(
        select(User).where(User.id == session_user_id, User.tenant_id == client.tenant_id)
    )
    if user is None:
        request.session.clear()
        return _park(request, client, pending)
    reason = await access_denial_reason(db, client=client, user=user)
    if reason is not None:
        return await _deny(request, db, client, reason, user)
    if not client.saml_acs_url or not client.saml_entity_id:
        return await _deny(request, db, client, "app_not_set_up", user)

    request.session.pop(PENDING_SAML_KEY, None)
    first, last = split_name(user.display_name, user.email)
    nameid_kind = client.saml_nameid or "email"
    tenant = await db.scalar(select(Tenant).where(Tenant.id == client.tenant_id))
    attributes = {
        "email": user.email,
        # Slack's names.
        "User.Email": user.email,
        "first_name": first,
        "last_name": last,
        "name": user.display_name or user.email.split("@")[0],
        "role": role_claim(user, tenant) if tenant else "member",
    }
    if not last:
        attributes.pop("last_name")
    xml = build_response(
        cert=cert,
        issuer=entity_id(client.client_id),
        audience=client.saml_entity_id,
        acs_url=client.saml_acs_url,
        in_response_to=pending.get("r") or None,
        nameid_format=NAMEID_FORMATS.get(nameid_kind, NAMEID_FORMATS["email"]),
        nameid=str(user.id) if nameid_kind == "persistent" else user.email,
        attributes=attributes,
    )
    await record_app_event(
        db,
        tenant_id=client.tenant_id,
        event_type=AuditEventType.app_login,
        email=user.email,
        user_id=user.id,
        idp=user.idp,
        request=request,
        details={"app": client.name, "protocol": "saml"},
    )
    await db.commit()
    return _post_form(client.saml_acs_url, xml, pending.get("s") or "")


def _post_form(acs_url: str, xml: bytes, relay_state: str) -> HTMLResponse:
    fields = f'<input type="hidden" name="SAMLResponse" value="{base64.b64encode(xml).decode()}">'
    if relay_state:
        fields += f'<input type="hidden" name="RelayState" value="{html.escape(relay_state)}">'
    page = (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Signing in</title></head>"
        '<body onload="document.forms[0].submit()">'
        f'<form method="post" action="{html.escape(acs_url)}">{fields}'
        "<noscript><p>Your browser has JavaScript turned off.</p>"
        '<button type="submit">Continue</button></noscript></form></body></html>'
    )
    return HTMLResponse(page)
