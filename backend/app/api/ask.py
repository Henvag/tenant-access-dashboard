"""Workspace Ask: answers questions about this company, with no setup.

By default Ask uses the built-in model on Cloudflare Workers AI, paid for by
Tenant Access and capped per plan per day. A company can add its own paid
Gemini key instead, which has no daily cap here. Only the number of questions
is stored, never the questions or answers. Paid ChatGPT/Claude live in Agents.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import workspace_briefing
from app.agents.providers import DEFAULT_MODEL, MODELS, complete
from app.agents.secrets import decrypt_secret, encrypt_secret, key_hint
from app.api.deps import get_current_user, require_admin
from app.billing.plans import limits_for_tenant
from app.config import settings
from app.db import get_db
from app.models import Tenant, User, UserRole

router = APIRouter(prefix="/ask", tags=["ask"])

ASK_MODELS = MODELS["google"]
DEFAULT_ASK_MODEL = DEFAULT_MODEL["google"]


BUILTIN_LABEL = "Gemma 4"


def builtin_available() -> bool:
    return bool(settings.cloudflare_account_id and settings.cloudflare_ai_token)


def ask_available(tenant: Tenant) -> bool:
    """Whether people in this company can ask right now (ignoring today's cap)."""
    return bool(tenant.ask_enabled) and (bool(tenant.ask_secret) or builtin_available())


def _today():
    return datetime.now(UTC).date()


def _used_today(tenant: Tenant) -> int:
    return tenant.ask_usage_count if tenant.ask_usage_day == _today() else 0


class AskStatusOut(BaseModel):
    # configured: people can ask. Kept under this name for older clients.
    configured: bool
    enabled: bool = True
    # "builtin" (no setup), "own_key" (the company's Gemini key) or None.
    source: str | None = None
    model: str | None = None
    key_hint: str | None = None
    # Built-in model only: questions asked today and the plan's daily cap.
    used_today: int | None = None
    daily_limit: int | None = None
    can_turn_off: bool = False


class AskEnabledIn(BaseModel):
    enabled: bool


def _status(user: User) -> AskStatusOut:
    tenant = user.tenant
    own_key = bool(tenant.ask_secret)
    source = "own_key" if own_key else ("builtin" if builtin_available() else None)
    is_admin = user.role == UserRole.admin
    out = AskStatusOut(
        configured=ask_available(tenant),
        enabled=bool(tenant.ask_enabled),
        source=source,
        model=(tenant.ask_model if own_key else BUILTIN_LABEL) if source else None,
        key_hint=tenant.ask_key_hint if own_key and is_admin else None,
        can_turn_off=tenant.owner_user_id is not None and tenant.owner_user_id == user.id,
    )
    if source == "builtin":
        out.used_today = _used_today(tenant)
        out.daily_limit = limits_for_tenant(tenant).ask_daily_questions
    return out


class AskConfigIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=400)
    model: str = Field(default="", validate_default=True)

    @field_validator("api_key")
    @classmethod
    def _key(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 8:
            raise ValueError("agent_key_required")
        return cleaned

    @field_validator("model")
    @classmethod
    def _model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return DEFAULT_ASK_MODEL
        if cleaned not in ASK_MODELS:
            raise ValueError("model_not_allowed")
        return cleaned


class ChatMessage(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        if value not in {"user", "assistant"}:
            raise ValueError("role_not_allowed")
        return value


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)


class ChatOut(BaseModel):
    content: str


@router.get("", response_model=AskStatusOut)
async def ask_status(user: User = Depends(get_current_user)) -> AskStatusOut:
    return _status(user)


@router.put("", response_model=AskStatusOut)
async def configure_ask(
    body: AskConfigIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AskStatusOut:
    tenant = await db.get(Tenant, admin.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_missing")
    tenant.ask_secret = encrypt_secret(body.api_key)
    tenant.ask_key_hint = key_hint(body.api_key)
    tenant.ask_model = body.model
    await db.commit()
    return _status(admin)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_ask(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    tenant = await db.get(Tenant, admin.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_missing")
    tenant.ask_secret = None
    tenant.ask_key_hint = None
    tenant.ask_model = None
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/enabled", response_model=AskStatusOut)
async def set_ask_enabled(
    body: AskEnabledIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AskStatusOut:
    """Owner only: turn Ask off (or back on) for the whole company."""
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tenant_missing")
    if tenant.owner_user_id is None or tenant.owner_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner_required")
    tenant.ask_enabled = body.enabled
    await db.commit()
    return _status(user)


async def _reserve_question(db: AsyncSession, tenant: Tenant) -> bool:
    """Count one built-in question for today. False when the plan's cap is used up.

    One UPDATE, so two people asking at once can't both take the last question.
    """
    today = _today()
    limit = limits_for_tenant(tenant).ask_daily_questions
    same_day = Tenant.ask_usage_day == today
    result = await db.execute(
        update(Tenant)
        .where(Tenant.id == tenant.id)
        .where((Tenant.ask_usage_day.is_distinct_from(today)) | (Tenant.ask_usage_count < limit))
        .values(
            ask_usage_count=case((same_day, Tenant.ask_usage_count + 1), else_=1),
            ask_usage_day=today,
        )
        .returning(Tenant.ask_usage_count)
        .execution_options(synchronize_session=False)
    )
    reserved = result.scalar_one_or_none() is not None
    await db.commit()
    return reserved


async def _refund_question(db: AsyncSession, tenant: Tenant) -> None:
    """The model call failed, so the question doesn't count."""
    await db.execute(
        update(Tenant)
        .where(Tenant.id == tenant.id)
        .where(Tenant.ask_usage_day == _today())
        .where(Tenant.ask_usage_count > 0)
        .values(ask_usage_count=Tenant.ask_usage_count - 1)
        .execution_options(synchronize_session=False)
    )
    await db.commit()


@router.post("/chat", response_model=ChatOut)
async def ask_chat(
    body: ChatIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    tenant = user.tenant
    if not tenant.ask_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ask_turned_off")
    own_key = bool(tenant.ask_secret and tenant.ask_model)
    if not own_key and not builtin_available():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ask_not_configured")
    if body.messages[-1].role != "user":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="agent_chat_failed")
    who = user.display_name or user.email
    question = body.messages[-1].content
    system = (
        f"You are the workspace assistant for {tenant.name}. "
        f"The person talking to you is signed in to Tenant Access as {who} ({user.email}). "
        "Answer questions about this company workspace clearly and briefly, using only the "
        "workspace details below. If the details don't cover the question, say so. "
        "Answer in the language the person writes in (for example Norwegian bokmål or English). "
        "Use simple Markdown: **bold**, numbered lists, and bullet lists with -. "
        "Do not use HTML. Prefer plain hyphen (-) over long dashes. Emoji are fine when they help. "
        "When you mention a tab, link it like [Billing](?view=billing)."
    )
    system = f"{system}\n\n{await workspace_briefing(db, user, question)}"
    messages = [{"role": item.role, "content": item.content} for item in body.messages]

    if not own_key and not await _reserve_question(db, tenant):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="ask_daily_limit"
        )
    try:
        if own_key:
            content = await complete(
                provider="google",
                model=tenant.ask_model,
                api_key=decrypt_secret(tenant.ask_secret),
                system=system,
                messages=messages,
            )
        else:
            content = await complete(
                provider="cloudflare",
                model=settings.ask_builtin_model,
                api_key=settings.cloudflare_ai_token,
                account_id=settings.cloudflare_account_id,
                system=system,
                messages=messages,
            )
    except httpx.HTTPStatusError as exc:
        if not own_key:
            await _refund_question(db, tenant)
        if exc.response is not None and exc.response.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="ask_rate_limited"
            ) from None
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="agent_chat_failed"
        ) from None
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        if not own_key:
            await _refund_question(db, tenant)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="agent_chat_failed"
        ) from None
    if not content.strip():
        if not own_key:
            await _refund_question(db, tenant)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="agent_chat_failed")
    return ChatOut(content=content)
