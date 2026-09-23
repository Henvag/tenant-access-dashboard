"""Rules for company AI agents, logos, and logout tokens."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from joserfc import jwt
from joserfc.jwk import RSAKey
from pydantic import ValidationError

from app.agents.providers import anthropic_payload, openai_payload
from app.agents.secrets import decrypt_secret, encrypt_secret, key_hint
from app.api.agents import AgentIn
from app.api.company import _accept_logo
from app.oauth.keys import _generate
from app.oauth.logout import _LOGOUT_EVENT, _logout_token
from app.schemas.app import _clean_logout


def test_agent_requires_a_known_provider_and_model() -> None:
    created = AgentIn(
        name="  Support  ",
        provider="openai",
        model="gpt-4o-mini",
        api_key="sk-test-key-1234",
    )
    assert created.name == "Support"
    assert created.provider == "openai"
    assert created.model == "gpt-4o-mini"
    with pytest.raises(ValidationError):
        AgentIn(name="Docs", provider="other", model="gpt-4o-mini", api_key="sk-test-key-1234")
    with pytest.raises(ValidationError):
        AgentIn(name="Docs", provider="openai", model="gpt-5-pro", api_key="sk-test-key-1234")


def test_api_key_round_trip_keeps_only_a_hint() -> None:
    token = encrypt_secret("sk-live-example-9876")
    assert token != "sk-live-example-9876"
    assert decrypt_secret(token) == "sk-live-example-9876"
    assert key_hint("sk-live-example-9876") == "9876"


def test_provider_payloads_name_the_signed_in_company_account() -> None:
    messages = [{"role": "user", "content": "Hello"}]
    openai = openai_payload("gpt-4o-mini", "signed in as ada", messages)
    assert openai["messages"][0]["role"] == "system"
    assert openai["messages"][1]["content"] == "Hello"
    anthropic = anthropic_payload("claude-haiku-4-5", "signed in as ada", messages)
    assert anthropic["system"] == "signed in as ada"
    assert anthropic["messages"][0]["role"] == "user"


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

