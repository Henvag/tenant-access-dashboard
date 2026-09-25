"""Rules for company AI agents, logos, logout tokens, and workspace Ask."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from joserfc import jwt
from joserfc.jwk import RSAKey
from pydantic import ValidationError

from app.agents.context import topics_for, workspace_briefing
from app.agents.providers import anthropic_payload, google_payload, openai_payload
from app.agents.secrets import decrypt_secret, encrypt_secret, key_hint
from app.api.agents import AgentIn
from app.api.ask import AskConfigIn
from app.api.company import _accept_logo
from app.models import UserRole
from app.oauth.keys import _generate
from app.oauth.logout import _LOGOUT_EVENT, _logout_token
from app.schemas.app import _clean_logout


def test_agent_requires_a_known_provider_and_model() -> None:
    created = AgentIn(
        name="  Support  ",
        provider="openai",
        model="gpt-6-astra",
        api_key="sk-test-key-1234",
    )
    assert created.name == "Support"
    assert created.provider == "openai"
    assert created.model == "gpt-6-astra"
    with pytest.raises(ValidationError):
        AgentIn(name="Docs", provider="other", model="gpt-6-astra", api_key="sk-test-key-1234")
    with pytest.raises(ValidationError):
        AgentIn(name="Docs", provider="openai", model="gpt-4o", api_key="sk-test-key-1234")
    # Gemini belongs under Ask, not Agents.
    with pytest.raises(ValidationError):
        AgentIn(name="Helper", provider="google", api_key="AIza-test-key-1234")


def test_ask_config_defaults_to_gemini_flash() -> None:
    configured = AskConfigIn(api_key="AIza-test-key-1234")
    assert configured.model == "gemini-3.5-flash-lite"
    with pytest.raises(ValidationError):
        AskConfigIn(api_key="AIza-test-key-1234", model="gpt-6-astra")


def test_api_key_round_trip_keeps_only_a_hint() -> None:
    token = encrypt_secret("sk-live-example-9876")
    assert token != "sk-live-example-9876"
    assert decrypt_secret(token) == "sk-live-example-9876"
    assert key_hint("sk-live-example-9876") == "9876"


def test_provider_payloads_name_the_signed_in_company_account() -> None:
    messages = [{"role": "user", "content": "Hello"}]
    openai = openai_payload("gpt-6-astra", "signed in as ada", messages)
    assert openai["messages"][0]["role"] == "system"
    assert openai["messages"][1]["content"] == "Hello"
    anthropic = anthropic_payload("claude-fable-5-1", "signed in as ada", messages)
    assert anthropic["system"] == "signed in as ada"
    assert anthropic["messages"][0]["role"] == "user"
    thread = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "Who am I?"},
    ]
    google = google_payload("signed in as ada", thread)
    assert google["system_instruction"]["parts"][0]["text"] == "signed in as ada"
    assert [turn["role"] for turn in google["contents"]] == ["user", "model", "user"]
    assert google["contents"][1]["parts"][0]["text"] == "Hi"
    assert "model" not in google


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    """Answers count queries with 0 and row queries with nothing."""

    async def scalar(self, _statement):
        return 0

    async def scalars(self, _statement):
        return _Scalars([])


@pytest.mark.asyncio
async def test_member_briefing_has_their_account_but_not_the_people_list() -> None:
    tenant = SimpleNamespace(
        name="Acme",
        workspace_domain="acme.com",
        owner_user_id=uuid4(),
        plan="free",
        plan_expires_at=None,
        stripe_subscription_id=None,
    )
    member = SimpleNamespace(
        id=uuid4(),
        email="bob@acme.com",
        display_name="Bob",
        role=UserRole.user,
        last_login_at=None,
        tenant=tenant,
    )
    text = await workspace_briefing(_FakeDb(), member)
    assert "Acme" in text and "@acme.com" in text
    assert "bob@acme.com" in text and "role user" in text
    assert "Apps they can open:" in text
    assert "People (up to" not in text
    assert "Recent activity" not in text
    assert "?view=overview" in text
    assert "?view=people" not in text

    admin = SimpleNamespace(**{**member.__dict__, "role": UserRole.admin, "id": tenant.owner_user_id})
    admin_text = await workspace_briefing(_FakeDb(), admin)
    assert "role owner" in admin_text
    assert "People (up to" in admin_text
    assert "Recent activity" in admin_text
    assert "?view=billing" in admin_text


def test_topics_for_maps_question_words() -> None:
    assert "people" in topics_for("Who is the owner?", is_admin=True)
    assert "billing" in topics_for("What plan are we on?", is_admin=False)
    assert "activity" in topics_for("What happened recently?", is_admin=True)
    assert "apps" in topics_for("Which apps can I open?", is_admin=False)
    # Empty question keeps the full role set.
    assert topics_for("", is_admin=True) >= {"product", "people", "apps", "activity", "billing"}
    assert "people" not in topics_for("", is_admin=False)


@pytest.mark.asyncio
async def test_question_aware_briefing_skips_heavy_sections() -> None:
    tenant = SimpleNamespace(
        name="Acme",
        workspace_domain="acme.com",
        owner_user_id=uuid4(),
        plan="free",
        plan_expires_at=None,
        stripe_subscription_id=None,
    )
    admin = SimpleNamespace(
        id=tenant.owner_user_id,
        email="ada@acme.com",
        display_name="Ada",
        role=UserRole.admin,
        last_login_at=None,
        tenant=tenant,
    )
    apps_only = await workspace_briefing(_FakeDb(), admin, "Which apps can I open?")
    assert "Apps they can open:" in apps_only
    assert "People (up to" not in apps_only
    assert "Recent activity" not in apps_only
    assert "Headroom:" not in apps_only

    people_q = await workspace_briefing(_FakeDb(), admin, "Who is the owner?")
    assert "People (up to" in people_q
    assert "Recent activity" not in people_q


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
