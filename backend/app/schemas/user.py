from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

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


class TenantUserOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    role: UserRole
    last_login_at: datetime | None

    model_config = {"from_attributes": True}
