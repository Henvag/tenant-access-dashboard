"""Workspace Ask: free Gemini Q&A about this company, separate from paid Agents."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context import workspace_briefing
from app.agents.providers import DEFAULT_MODEL, MODELS, complete
from app.agents.secrets import decrypt_secret, encrypt_secret, key_hint
from app.api.deps import get_current_user, require_admin
from app.db import get_db
from app.models import Tenant, User, UserRole

router = APIRouter(prefix="/ask", tags=["ask"])

ASK_MODELS = MODELS["google"]
DEFAULT_ASK_MODEL = DEFAULT_MODEL["google"]


class AskStatusOut(BaseModel):
    configured: bool
    model: str | None = None
    key_hint: str | None = None


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
    tenant = user.tenant
    configured = bool(tenant.ask_secret)
    return AskStatusOut(
        configured=configured,
        model=tenant.ask_model if configured else None,
        key_hint=tenant.ask_key_hint if configured and user.role == UserRole.admin else None,
    )


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
    return AskStatusOut(configured=True, model=tenant.ask_model, key_hint=tenant.ask_key_hint)


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


@router.post("/chat", response_model=ChatOut)
async def ask_chat(
    body: ChatIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    tenant = user.tenant
    if not tenant.ask_secret or not tenant.ask_model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ask_not_configured")
    if body.messages[-1].role != "user":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="agent_chat_failed")
    who = user.display_name or user.email
    question = body.messages[-1].content
    system = (
        f"You are the workspace assistant for {tenant.name}. "
        f"The person talking to you is signed in to Tenant Access as {who} ({user.email}). "
        "Answer questions about this company workspace clearly and briefly. "
        "Use simple Markdown: **bold**, numbered lists, and bullet lists with -. "
        "Do not use HTML. Prefer plain hyphen (-) over long dashes. Emoji are fine when they help. "
        "When you mention a tab, link it like [Billing](?view=billing)."
    )
    system = f"{system}\n\n{await workspace_briefing(db, user, question)}"
    try:
        content = await complete(
            provider="google",
            model=tenant.ask_model,
            api_key=decrypt_secret(tenant.ask_secret),
            system=system,
            messages=[{"role": item.role, "content": item.content} for item in body.messages],
        )
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="ask_rate_limited"
            ) from None
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="agent_chat_failed"
        ) from None
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="agent_chat_failed"
        ) from None
    if not content.strip():
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="agent_chat_failed")
    return ChatOut(content=content)
