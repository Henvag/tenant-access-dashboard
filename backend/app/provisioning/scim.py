"""A small SCIM 2.0 client for the user calls provisioning needs.

Written for Slack (https://api.slack.com/scim/v2), which is the only app that
uses it today, but it keeps to the SCIM standard (RFC 7643/7644) so another
SCIM app needs little more than a base URL and its own username rule.

Slack's quirks handled here:
- ``userName`` is the Slack handle: lowercase, at most 21 characters.
- An email that already belongs to a deactivated Slack account can't be used
  for a new one, so we always look the address up first and reactivate.
- Slack locks a user while it updates it and answers 429 with Retry-After.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

SLACK_BASE_URL = "https://api.slack.com/scim/v2"
KINDS = ("slack",)

_TIMEOUT = 10.0
_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
_PATCH_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:PatchOp"
_SCAN_PAGES = 20
_SCAN_PAGE_SIZE = 1000

# Tests swap this for an httpx.MockTransport.
_transport: httpx.AsyncBaseTransport | None = None


class ScimError(Exception):
    """``code`` is short and safe to show. ``retry_after`` is set when trying again may help."""

    def __init__(self, code: str, *, retry_after: float | None = None):
        super().__init__(code)
        self.code = code[:64]
        self.retry_after = retry_after


@dataclass
class RemoteUser:
    id: str
    active: bool


@dataclass
class Person:
    email: str
    display_name: str | None


def base_url_for(kind: str) -> str:
    return SLACK_BASE_URL


def _client(kind: str, token: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url_for(kind),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=_TIMEOUT,
        follow_redirects=False,
        transport=_transport,
    )


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        return ""
    if not isinstance(body, dict):
        return ""
    detail = body.get("detail") or body.get("Errors", {})
    if isinstance(detail, dict):
        detail = detail.get("description") or ""
    return str(detail or "").strip().lower()


def _raise_for(response: httpx.Response) -> None:
    status = response.status_code
    if status < 300:
        return
    if status == 429:
        try:
            wait = float(response.headers.get("retry-after", "30"))
        except ValueError:
            wait = 30.0
        raise ScimError("provision_rate_limited", retry_after=max(1.0, min(wait, 3600.0)))
    if status in (401, 403):
        raise ScimError("provision_key_rejected")
    if status >= 500:
        raise ScimError("provision_app_down", retry_after=60.0)
    detail = _detail(response)
    if detail and re.fullmatch(r"[a-z0-9_]{1,48}", detail):
        raise ScimError(f"slack_{detail}")
    raise ScimError("provision_app_error")


async def _send(http: httpx.AsyncClient, method: str, url: str, **kw) -> httpx.Response:
    try:
        return await http.request(method, url, **kw)
    except httpx.HTTPError as exc:
        raise ScimError("provision_unreachable", retry_after=60.0) from exc


def _remote(body: dict) -> RemoteUser:
    return RemoteUser(id=str(body["id"]), active=bool(body.get("active", True)))


def _has_email(body: dict, email: str) -> bool:
    for item in body.get("emails") or []:
        if isinstance(item, dict) and (item.get("value") or "").lower() == email:
            return True
    return False


def slack_username(email: str, attempt: int = 0) -> str:
    """Slack handle from the address: lowercase letters, digits, . _ - and at most 21 long."""
    local = email.split("@", 1)[0].lower()
    handle = re.sub(r"[^a-z0-9._-]", "", local).strip("._-") or "user"
    if attempt:
        suffix = str(attempt + 1)
        return handle[: 21 - len(suffix)] + suffix
    return handle[:21]


def _names(person: Person) -> tuple[str, str, str]:
    display = (person.display_name or "").strip() or person.email.split("@", 1)[0]
    given, _, family = display.partition(" ")
    return display, given, family


async def verify(kind: str, token: str) -> None:
    """Raise ScimError unless the token can list users."""
    async with _client(kind, token) as http:
        response = await _send(http, "GET", "/Users", params={"startIndex": 1, "count": 1})
        _raise_for(response)


async def find_by_email(http: httpx.AsyncClient, email: str) -> RemoteUser | None:
    email = email.lower()
    response = await _send(
        http, "GET", "/Users", params={"filter": f'email eq "{email}"', "count": 10}
    )
    if response.status_code == 400:
        # Not every SCIM server filters on email. Read the list instead.
        return await _scan_for_email(http, email)
    _raise_for(response)
    for body in response.json().get("Resources") or []:
        if _has_email(body, email):
            return _remote(body)
    return None


async def _scan_for_email(http: httpx.AsyncClient, email: str) -> RemoteUser | None:
    start = 1
    for _ in range(_SCAN_PAGES):
        response = await _send(
            http, "GET", "/Users", params={"startIndex": start, "count": _SCAN_PAGE_SIZE}
        )
        _raise_for(response)
        resources = response.json().get("Resources") or []
        for body in resources:
            if _has_email(body, email):
                return _remote(body)
        if len(resources) < _SCAN_PAGE_SIZE:
            return None
        start += len(resources)
    return None


async def get_user(http: httpx.AsyncClient, remote_id: str) -> RemoteUser | None:
    response = await _send(http, "GET", f"/Users/{remote_id}")
    if response.status_code == 404:
        return None
    _raise_for(response)
    return _remote(response.json())


async def create_user(http: httpx.AsyncClient, person: Person) -> RemoteUser:
    display, given, family = _names(person)
    last_error: ScimError | None = None
    for attempt in range(3):
        body = {
            "schemas": [_USER_SCHEMA],
            "userName": slack_username(person.email, attempt),
            "displayName": display,
            "name": {"givenName": given, "familyName": family},
            "emails": [{"value": person.email, "primary": True}],
            "active": True,
        }
        response = await _send(http, "POST", "/Users", json=body)
        try:
            _raise_for(response)
        except ScimError as exc:
            if exc.code == "slack_username_taken":
                last_error = exc
                continue
            raise
        return _remote(response.json())
    raise last_error or ScimError("provision_app_error")


async def set_active(http: httpx.AsyncClient, remote_id: str, active: bool) -> None:
    body = {
        "schemas": [_PATCH_SCHEMA],
        "Operations": [{"op": "replace", "path": "active", "value": active}],
    }
    response = await _send(http, "PATCH", f"/Users/{remote_id}", json=body)
    _raise_for(response)


def client_for(kind: str, token: str) -> httpx.AsyncClient:
    return _client(kind, token)
