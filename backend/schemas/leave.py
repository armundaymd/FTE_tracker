import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

LeaveType = Literal[
    "FMLA",
    "LOA",
    "Research Protected Time",
    "Maternity/Paternity",
    "Medical",
    "Administrative",
    "Other",
]


class LeaveBase(BaseModel):
    physician_id: uuid.UUID
    leave_type: LeaveType
    start_date: date
    end_date: date
    notes: Optional[str] = None
    is_partial: bool = False
    fte_during_leave: Optional[Decimal] = Field(None, ge=0, le=1)

    @model_validator(mode="after")
    def end_on_or_after_start(self) -> "LeaveBase":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class LeaveCreate(LeaveBase):
    pass


class LeaveUpdate(BaseModel):
    leave_type: Optional[LeaveType] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    is_partial: Optional[bool] = None
    fte_during_leave: Optional[Decimal] = Field(None, ge=0, le=1)


class LeaveRead(LeaveBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_by: Optional[uuid.UUID] = None   # FK to users.id — Phase 2
    created_at: datetime
    updated_at: datetime
