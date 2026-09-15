import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[uuid.UUID] = None
    user_email: Optional[str] = None
    action: str
    table_name: str
    record_id: Optional[uuid.UUID] = None
    old_values: Optional[dict[str, Any]] = None
    new_values: Optional[dict[str, Any]] = None
    notes: Optional[str] = None
    created_at: datetime
