from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domain import normalize_workspace_domain


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    workspace_domain: str = Field(min_length=3, max_length=253)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("name_required")
        return cleaned

    @field_validator("workspace_domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        try:
            return normalize_workspace_domain(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class TenantOut(BaseModel):
    id: UUID
    name: str
    workspace_domain: str
    created_at: datetime

    model_config = {"from_attributes": True}
