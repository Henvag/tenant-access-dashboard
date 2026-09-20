from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

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
    is_owner: bool = False


class TenantUserOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    role: UserRole
    last_login_at: datetime | None
    disabled: bool = False
    is_owner: bool = False

    model_config = {"from_attributes": True}


class UserPatch(BaseModel):
    """One change per request: either access (disabled) or role."""

    disabled: bool | None = Field(default=None)
    role: UserRole | None = Field(default=None)

    @model_validator(mode="after")
    def exactly_one_field(self) -> "UserPatch":
        has_disabled = self.disabled is not None
        has_role = self.role is not None
        if has_disabled == has_role:
            raise ValueError("provide_exactly_one_of_disabled_or_role")
        return self
