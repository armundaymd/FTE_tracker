import uuid
from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel


class FTEHistoryEntry(BaseModel):
    date: date
    type: Literal["assignment", "role", "leave"]
    description: str
    change_reason: Optional[str] = None
    detail: Dict[str, Any]


class FTEHistoryResponse(BaseModel):
    physician_id: uuid.UUID
    entries: List[FTEHistoryEntry]
