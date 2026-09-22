"""Rules for logout tokens, company logos, and shared agent links."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from joserfc import jwt
from joserfc.jwk import RSAKey
from pydantic import ValidationError

from app.api.agents import AgentIn
from app.api.company import _accept_logo
from app.oauth.keys import _generate
from app.oauth.logout import _LOGOUT_EVENT, _logout_token
from app.schemas.app import _clean_logout


def test_agent_links_are_https_without_a_fragment() -> None:
    created = AgentIn(name="  Docs  ", url="https://example.com/tools")
    assert created.name == "Docs"
    assert created.url == "https://example.com/tools"
    with pytest.raises(ValidationError):
        AgentIn(name="Docs", url="http://example.com")
    with pytest.raises(ValidationError):
        AgentIn(name="Docs", url="https://example.com/tools#section")


def test_logo_rejects_script_and_oversized_files() -> None:
    png = _accept_logo("image/png", b"\x89PNG")
    assert png == "image/png"
    with pytest.raises(HTTPException) as script:
        _accept_logo("image/svg+xml", b"<svg><script>alert(1)</script></svg>")
    assert script.value.detail == "logo_type"
    with pytest.raises(HTTPException) as huge:
        _accept_logo("image/jpeg", b"x" * 200_001)
    assert huge.value.detail == "logo_too_large"


def test_logout_url_must_be_https() -> None:
    assert _clean_logout("https://app.example/logout") == "https://app.example/logout"
    assert _clean_logout("  ") is None
    with pytest.raises(ValueError):
        _clean_logout("http://app.example/logout")


def test_logout_token_carries_the_backchannel_event() -> None:
    key = _generate()
    user = SimpleNamespace(id=uuid4())
    token = _logout_token(key, user=user, audience="grafana")
    decoded = jwt.decode(token, RSAKey.import_key(key.public_pem))
    assert decoded.header["typ"] == "logout+jwt"
    assert decoded.claims["aud"] == "grafana"
    assert decoded.claims["sub"] == str(user.id)
    assert decoded.claims["events"][_LOGOUT_EVENT] == {}
    assert "nonce" not in decoded.claims
