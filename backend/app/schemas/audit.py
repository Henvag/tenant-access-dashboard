from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models import AuditEventType, IdentityProvider


class AuditEventOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None = None
    event_type: AuditEventType
    idp: IdentityProvider
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
