"""Shared agent links in the sidebar. Separate from OIDC apps."""

from __future__ import annotations

from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db import get_db
from app.models import TeamAgent, User

router = APIRouter(prefix="/agents", tags=["agents"])

MAX_AGENTS = 20


class AgentOut(BaseModel):
    id: UUID
    name: str
    url: str
    position: int


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name is required")
        return cleaned

    @field_validator("url")
    @classmethod
    def _url(cls, value: str) -> str:
        cleaned = value.strip()
        parts = urlsplit(cleaned)
        if parts.scheme != "https" or not parts.netloc or parts.fragment:
            raise ValueError("https_url_required")
        return cleaned


def _out(row: TeamAgent) -> AgentOut:
    return AgentOut(id=row.id, name=row.name, url=row.url, position=row.position)


@router.get("", response_model=list[AgentOut])
async def list_agents(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentOut]:
    rows = (
        await db.scalars(select(TeamAgent).order_by(TeamAgent.position, TeamAgent.created_at))
    ).all()
    return [_out(row) for row in rows]


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
        url=body.url,
        position=int(count),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _out(row)


@router.patch("/{agent_id}", response_model=AgentOut)
async def patch_agent(
    agent_id: UUID,
    body: AgentIn,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AgentOut:
    row = await db.get(TeamAgent, agent_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent_not_found")
    row.name = body.name
    row.url = body.url
    await db.commit()
    return _out(row)


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
