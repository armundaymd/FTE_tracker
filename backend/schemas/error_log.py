import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ErrorLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    error_id: str
    method: str
    path: str
    exception_type: str
    message: str
    traceback: str
    user_id: Optional[uuid.UUID] = None
    user_email: Optional[str] = None
    created_at: datetime
