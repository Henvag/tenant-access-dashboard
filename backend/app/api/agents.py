"""Company AI agents. Sign-in is the Tenant Access session; the provider bills the company."""

from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.providers import DEFAULT_MODEL, MODELS, complete
from app.agents.secrets import decrypt_secret, encrypt_secret, key_hint
from app.api.deps import get_current_user, require_admin
from app.db import get_db
from app.models import AccessPolicy, TeamAgent, User, UserRole

router = APIRouter(prefix="/agents", tags=["agents"])

MAX_AGENTS = 20


class AgentOut(BaseModel):
    id: UUID
    name: str
    provider: str
    model: str
    key_hint: str
    access_policy: AccessPolicy
    position: int


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    provider: str
    model: str = ""
    api_key: str = Field(min_length=8, max_length=400)
    access_policy: AccessPolicy = AccessPolicy.everyone

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("provider")
    @classmethod
    def _provider(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in MODELS:
            raise ValueError("unknown_provider")
        return cleaned

    @field_validator("model")
    @classmethod
    def _model(cls, value: str, info) -> str:
        provider = info.data.get("provider")
        allowed = MODELS.get(provider or "", ())
        cleaned = value.strip()
        if not cleaned:
            return DEFAULT_MODEL.get(provider or "", "")
        if cleaned not in allowed:
            raise ValueError("model_not_allowed")
        return cleaned

    @field_validator("api_key")
    @classmethod
    def _key(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 8:
            raise ValueError("agent_key_required")
        return cleaned

    @field_validator("access_policy")
    @classmethod
    def _policy(cls, value: AccessPolicy) -> AccessPolicy:
        if value == AccessPolicy.assigned:
            raise ValueError("policy_not_supported")
        return value


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


def _out(row: TeamAgent) -> AgentOut:
    return AgentOut(
        id=row.id,
        name=row.name,
        provider=row.provider,
        model=row.model,
        key_hint=row.key_hint,
        access_policy=row.access_policy,
        position=row.position,
    )


def _visible(row: TeamAgent, user: User) -> bool:
    if row.access_policy == AccessPolicy.everyone:
        return True
    return user.role == UserRole.admin


@router.get("", response_model=list[AgentOut])
async def list_agents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentOut]:
    rows = (
        await db.scalars(select(TeamAgent).order_by(TeamAgent.position, TeamAgent.created_at))
    ).all()
    return [_out(row) for row in rows if _visible(row, user)]


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AgentOut:
    count = await db.scalar(select(func.count()).select_from(TeamAgent)) or 0
    if count >= MAX_AGENTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="agent_limit_reached")
    row = TeamAgent(
        tenant_id=admin.tenant_id,
        name=body.name,
        provider=body.provider,
        model=body.model,
        secret=encrypt_secret(body.api_key),
        key_hint=key_hint(body.api_key),
        access_policy=body.access_policy,
        position=int(count),
    )
    db.add(row)
    await db.flush()
    out = _out(row)
    await db.commit()
    return out


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await db.get(TeamAgent, agent_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_not_found")
    await db.delete(row)
    await db.commit()


@router.post("/{agent_id}/chat", response_model=ChatOut)
async def chat(
    agent_id: UUID,
    body: ChatIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatOut:
    row = await db.get(TeamAgent, agent_id)
    if row is None or not _visible(row, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_not_found")
    if body.messages[-1].role != "user":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="agent_chat_failed")
    who = user.display_name or user.email
    system = (
        f"You are {row.name} for the company workspace. "
        f"The person talking to you is signed in to Tenant Access as {who} ({user.email})."
    )
    try:
        api_key = decrypt_secret(row.secret)
        content = await complete(
            provider=row.provider,
            model=row.model,
            api_key=api_key,
            system=system,
            messages=[{"role": item.role, "content": item.content} for item in body.messages],
        )
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="agent_chat_failed"
        ) from None
    if not content.strip():
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="agent_chat_failed")
    return ChatOut(content=content)
