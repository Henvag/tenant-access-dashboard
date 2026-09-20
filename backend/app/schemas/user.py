from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import UserRole


class MeOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    role: UserRole
    tenant_id: UUID
    tenant_name: str
    workspace_domain: str
    last_login_at: datetime | None
    disabled: bool = False


class TenantUserOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    role: UserRole
    last_login_at: datetime | None
    disabled: bool = False

    model_config = {"from_attributes": True}


class UserDisabledUpdate(BaseModel):
    disabled: bool = Field(description="True to disable access; false to re-enable.")

