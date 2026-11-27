"""Sign a person out of apps that ignore OIDC back-channel logout.

Grafana, Outline and Gitea keep their own login cookie. An admin can store an
admin credential for such an app; when someone is disabled we use the app's
own admin API:

- Grafana: revoke all of the person's sessions (POST /api/admin/users/:id/logout).
  Needs a Grafana server admin's "username:password"; Grafana does not accept
  service account tokens on its admin API.
- Outline: suspend the person (POST /api/users.suspend). Needs an admin's API key.
  Re-enabling them in Tenant Access un-suspends them (users.activate).
- Gitea: set "prohibit login" (PATCH /api/v1/admin/users/:name). Needs an admin
  access token with the admin scope. Re-enabling lifts it again.

Every call is bounded by a short timeout and never blocks the disable itself.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

import httpx

from app.webhooks.service import WebhookUrlError, assert_public_host, validate_url_shape

logger = logging.getLogger("app.connectors")

KINDS = ("grafana", "outline", "gitea")

# Results stored in the audit entry, next to logout.LOGGED_OUT etc.
SIGNED_OUT = "logged_out"
SUSPENDED = "suspended"
NO_ACCOUNT = "no_account"
FAILED = "failed"
RESTORED = "restored"

_TIMEOUT = 5.0
_GITEA_PAGES = 40

# Tests swap this for an httpx.MockTransport.
_transport: httpx.AsyncBaseTransport | None = None


class ConnectorError(Exception):
    """Short error code for the dashboard, e.g. ``signout_key_rejected``."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class Connector:
    kind: str
    base_url: str
    secret: str

    @property
    def root(self) -> str:
        return self.base_url.rstrip("/")


def _code(exc: WebhookUrlError) -> str:
    code = exc.args[0]
    if code == "https_url_required":
        return "signout_https_required"
    return code.replace("webhook_", "signout_")


def clean_base_url(value: str) -> str:
    try:
        return validate_url_shape(value).rstrip("/")
    except WebhookUrlError as exc:
        raise ConnectorError(_code(exc)) from exc


def _headers(conn: Connector) -> dict[str, str]:
    if conn.kind == "grafana":
        token = base64.b64encode(conn.secret.encode()).decode()
        return {"Authorization": f"Basic {token}", "Accept": "application/json"}
    if conn.kind == "outline":
        return {"Authorization": f"Bearer {conn.secret}", "Accept": "application/json"}
    return {"Authorization": f"token {conn.secret}", "Accept": "application/json"}


async def _client(conn: Connector) -> httpx.AsyncClient:
    try:
        await assert_public_host(conn.root)
    except WebhookUrlError as exc:
        raise ConnectorError(_code(exc)) from exc
    return httpx.AsyncClient(
        base_url=conn.root,
        headers=_headers(conn),
        timeout=_TIMEOUT,
        follow_redirects=False,
        transport=_transport,
    )


def _check(response: httpx.Response) -> None:
    if response.status_code in (401, 403):
        raise ConnectorError("signout_key_rejected")
    if response.status_code >= 300:
        raise ConnectorError("signout_app_error")


async def verify(conn: Connector) -> None:
    """Raise ConnectorError unless the credential can do what sign-out needs."""
    try:
        async with await _client(conn) as http:
            if conn.kind == "grafana":
                _check(await http.get("/api/users", params={"perpage": 1}))
            elif conn.kind == "outline":
                response = await http.post("/api/auth.info", json={})
                _check(response)
                role = ((response.json().get("data") or {}).get("user") or {}).get("role")
                if role and role != "admin":
                    raise ConnectorError("signout_not_admin")
            else:
                _check(await http.get("/api/v1/admin/users", params={"limit": 1}))
    except httpx.HTTPError as exc:
        raise ConnectorError("signout_unreachable") from exc
    except ValueError as exc:
        raise ConnectorError("signout_app_error") from exc


async def _find(http: httpx.AsyncClient, conn: Connector, email: str) -> dict | None:
    email = email.lower()
    if conn.kind == "grafana":
        response = await http.get("/api/users/lookup", params={"loginOrEmail": email})
        if response.status_code == 404:
            return None
        _check(response)
        return response.json()
    if conn.kind == "outline":
        response = await http.post(
            "/api/users.list", json={"query": email, "filter": "all", "limit": 25}
        )
        _check(response)
        for user in response.json().get("data") or []:
            if (user.get("email") or "").lower() == email:
                return user
        return None
    for page in range(1, _GITEA_PAGES + 1):
        response = await http.get("/api/v1/admin/users", params={"limit": 50, "page": page})
        _check(response)
        users = response.json()
        if not users:
            return None
        for user in users:
            if (user.get("email") or "").lower() == email:
                return user
    return None


async def sign_out(conn: Connector, email: str) -> str:
    """End the person's sessions in the app. Returns a result for the audit log."""
    try:
        async with await _client(conn) as http:
            user = await _find(http, conn, email)
            if user is None:
                return NO_ACCOUNT
            if conn.kind == "grafana":
                _check(await http.post(f"/api/admin/users/{user['id']}/logout"))
                return SIGNED_OUT
            if conn.kind == "outline":
                _check(await http.post("/api/users.suspend", json={"id": user["id"]}))
                return SUSPENDED
            await _set_gitea_prohibit(http, user, True)
            return SUSPENDED
    except (ConnectorError, httpx.HTTPError, ValueError, KeyError) as exc:
        logger.info("sign-out via %s failed: %s", conn.kind, exc)
        return FAILED


async def restore(conn: Connector, email: str) -> str:
    """Undo a suspension when the person is re-enabled. Grafana needs nothing."""
    try:
        async with await _client(conn) as http:
            user = await _find(http, conn, email)
            if user is None:
                return NO_ACCOUNT
            if conn.kind == "outline":
                _check(await http.post("/api/users.activate", json={"id": user["id"]}))
            elif conn.kind == "gitea":
                await _set_gitea_prohibit(http, user, False)
            return RESTORED
    except (ConnectorError, httpx.HTTPError, ValueError, KeyError) as exc:
        logger.info("restore via %s failed: %s", conn.kind, exc)
        return FAILED


async def _set_gitea_prohibit(http: httpx.AsyncClient, user: dict, prohibit: bool) -> None:
    # Gitea requires the login source fields on every admin edit.
    body = {
        "prohibit_login": prohibit,
        "source_id": user.get("source_id", 0),
        "login_name": user.get("login_name") or user["login"],
    }
    _check(await http.patch(f"/api/v1/admin/users/{user['login']}", json=body))
