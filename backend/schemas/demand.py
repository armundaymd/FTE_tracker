import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MonthlyDemandBase(BaseModel):
    site_id: uuid.UUID
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)
    hours_required: Decimal = Field(Decimal("0"), ge=0)
    notes: Optional[str] = None


class MonthlyDemandCreate(MonthlyDemandBase):
    pass


class MonthlyDemandUpdate(BaseModel):
    hours_required: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None


class MonthlyDemandRead(MonthlyDemandBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    updated_by: Optional[uuid.UUID] = None   # FK to users.id — Phase 2
    updated_at: datetime


class MonthlyDemandUpsert(BaseModel):
    """Single-cell upsert payload used by the 12-month grid editor."""

    hours_required: Decimal = Field(..., ge=0)
    notes: Optional[str] = None


class BulkDemandUpsert(BaseModel):
    """Bulk upsert for an entire site+year grid in one request."""

    site_id: uuid.UUID
    year: int = Field(..., ge=2020, le=2100)
    rows: List[MonthlyDemandUpsert] = Field(..., min_length=1, max_length=12)
