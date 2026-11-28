"""Built-in Ask: works with no setup, counts questions per plan, owner can turn it off."""

from datetime import timedelta
from uuid import uuid4

import pytest
from app.agents.providers import openai_payload
from app.api import ask as ask_api
from app.api.ask import (
    AskEnabledIn,
    ChatIn,
    ChatMessage,
    ask_chat,
    ask_status,
    set_ask_enabled,
)
from app.auth.rls import set_tenant_rls
from app.billing.plans import PlanId, limits_for
from app.config import settings
from app.models import IdentityProvider, Tenant, User, UserRole
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

pytestmark = pytest.mark.asyncio


@pytest.fixture
def builtin_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "cloudflare_account_id", "acct")
    monkeypatch.setattr(settings, "cloudflare_ai_token", "token")
    calls: list[dict] = []

    async def fake_complete(**kwargs):
        calls.append(kwargs)
        return "Ada is the owner."

    monkeypatch.setattr(ask_api, "complete", fake_complete)
    return calls


async def _seed(factory: async_sessionmaker[AsyncSession]) -> tuple:
    suffix = uuid4().hex[:8]
    domain = f"ask-{suffix}.com"
    async with factory() as session:
        tenant = Tenant(name=f"Ask {suffix}", workspace_domain=domain)
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
    async with factory() as session:
        await set_tenant_rls(session, tenant.id)
        owner = User(
            tenant_id=tenant.id,
            email=f"ada@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"ada-{suffix}",
            role=UserRole.admin,
        )
        member = User(
            tenant_id=tenant.id,
            email=f"bo@{domain}",
            idp=IdentityProvider.google,
            oidc_sub=f"bo-{suffix}",
            role=UserRole.user,
        )
        session.add_all([owner, member])
        await session.flush()
        row = await session.get(Tenant, tenant.id)
        row.owner_user_id = owner.id
        await session.commit()
        return tenant.id, owner.id, member.id


async def _user(session: AsyncSession, tenant_id, user_id) -> User:
    await set_tenant_rls(session, tenant_id)
    return await session.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.tenant))
    )


def _question(text: str = "Who is the owner?") -> ChatIn:
    return ChatIn(messages=[ChatMessage(role="user", content=text)])


async def test_ask_works_without_setup(app_session_factory, builtin_on) -> None:
    tenant_id, _, member_id = await _seed(app_session_factory)
    async with app_session_factory() as session:
        member = await _user(session, tenant_id, member_id)
        status = await ask_status(member)
        assert status.configured is True
        assert status.source == "builtin"
        assert status.used_today == 0
        assert status.daily_limit == limits_for(PlanId.free).ask_daily_questions
        assert status.can_turn_off is False

        reply = await ask_chat(_question(), member, session)
        assert reply.content == "Ada is the owner."
        assert builtin_on[0]["provider"] == "cloudflare"
        assert builtin_on[0]["model"] == settings.ask_builtin_model
        assert builtin_on[0]["account_id"] == "acct"
        # Only this company's details go to the model.
        assert member.tenant.name in builtin_on[0]["system"]

    async with app_session_factory() as session:
        member = await _user(session, tenant_id, member_id)
        assert (await ask_status(member)).used_today == 1


async def test_daily_cap_per_plan_and_reset(app_session_factory, builtin_on) -> None:
    tenant_id, _, member_id = await _seed(app_session_factory)
    limit = limits_for(PlanId.free).ask_daily_questions
    async with app_session_factory() as session:
        member = await _user(session, tenant_id, member_id)
        member.tenant.ask_usage_day = ask_api._today()
        member.tenant.ask_usage_count = limit
        await session.commit()
        with pytest.raises(HTTPException) as exc:
            await ask_chat(_question(), member, session)
        assert exc.value.status_code == 429
        assert exc.value.detail == "ask_daily_limit"
        assert builtin_on == []

        # A new day starts the count again.
        member.tenant.ask_usage_day = ask_api._today() - timedelta(days=1)
        await session.commit()
        await ask_chat(_question(), member, session)
        await session.refresh(member.tenant)
        assert member.tenant.ask_usage_count == 1
        assert member.tenant.ask_usage_day == ask_api._today()


async def test_failed_model_call_does_not_count(app_session_factory, monkeypatch) -> None:
    monkeypatch.setattr(settings, "cloudflare_account_id", "acct")
    monkeypatch.setattr(settings, "cloudflare_ai_token", "token")

    async def broken(**kwargs):
        raise ValueError("bad response")

    monkeypatch.setattr(ask_api, "complete", broken)
    tenant_id, _, member_id = await _seed(app_session_factory)
    async with app_session_factory() as session:
        member = await _user(session, tenant_id, member_id)
        with pytest.raises(HTTPException) as exc:
            await ask_chat(_question(), member, session)
        assert exc.value.status_code == 502
        await session.refresh(member.tenant)
        assert member.tenant.ask_usage_count == 0


async def test_only_owner_can_turn_ask_off(app_session_factory, builtin_on) -> None:
    tenant_id, owner_id, member_id = await _seed(app_session_factory)
    async with app_session_factory() as session:
        member = await _user(session, tenant_id, member_id)
        with pytest.raises(HTTPException) as exc:
            await set_ask_enabled(AskEnabledIn(enabled=False), member, session)
        assert exc.value.detail == "owner_required"

    async with app_session_factory() as session:
        owner = await _user(session, tenant_id, owner_id)
        status = await set_ask_enabled(AskEnabledIn(enabled=False), owner, session)
        assert status.enabled is False
        assert status.configured is False

    async with app_session_factory() as session:
        member = await _user(session, tenant_id, member_id)
        with pytest.raises(HTTPException) as exc:
            await ask_chat(_question(), member, session)
        assert exc.value.detail == "ask_turned_off"
        assert builtin_on == []


async def test_no_builtin_token_means_not_configured(app_session_factory, monkeypatch) -> None:
    monkeypatch.setattr(settings, "cloudflare_ai_token", "")
    tenant_id, _, member_id = await _seed(app_session_factory)
    async with app_session_factory() as session:
        member = await _user(session, tenant_id, member_id)
        assert (await ask_status(member)).configured is False
        with pytest.raises(HTTPException) as exc:
            await ask_chat(_question(), member, session)
        assert exc.value.detail == "ask_not_configured"


def test_cloudflare_payload_is_openai_shaped() -> None:
    payload = openai_payload("@cf/google/gemma-4-26b-a4b-it", "sys", [{"role": "user", "content": "Hei"}])
    assert payload["messages"][0] == {"role": "system", "content": "sys"}
    assert payload["model"] == "@cf/google/gemma-4-26b-a4b-it"
