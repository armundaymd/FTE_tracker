import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Lookup ───────────────────────────────────────────────────────────────────

class TimeCategoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_clinical: bool
    display_order: int


# ── Single row ───────────────────────────────────────────────────────────────

class TimeAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    physician_id: uuid.UUID
    site_id: Optional[uuid.UUID] = None
    time_category_id: int
    year: int
    month: int
    hours: Decimal
    change_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ── Grid read (GET /api/physicians/{id}/time-allocations?year=) ────────────
#
# Shaped so the frontend can render a category x month table with no further
# assembly: one row per time_category (in display_order, already carrying
# is_clinical so the frontend can group Clinical vs. Non-clinical sections),
# each row's `cells` normally holds 12 entries — one per month, hours=0 for
# anything not yet entered. A cell list can exceed 12 only in the edge case
# of a category having rows at more than one site in the same month; the
# grid preserves that rather than silently collapsing it, since the same
# data has to round-trip through TimeAllocationBulkUpsert below.
#
# Running totals are precomputed here (rather than left to the frontend)
# because the same "Total Hrs Check" math also has to run server-side, in
# the same transaction, to keep physicians.clinical_pct and
# needs_time_allocation_config in sync — computing it once and returning it
# avoids two implementations of the same arithmetic drifting apart.

class TimeAllocationCell(BaseModel):
    site_id: Optional[uuid.UUID] = None
    month: int = Field(..., ge=1, le=12)
    hours: Decimal
    change_reason: Optional[str] = None


class TimeAllocationCategoryRow(BaseModel):
    time_category_id: int
    category_name: str
    is_clinical: bool
    cells: List[TimeAllocationCell]
    category_total_hours: Decimal


class TimeAllocationGrid(BaseModel):
    physician_id: uuid.UUID
    year: int
    yearly_hours: int                       # physicians.yearly_hours — what allocated hours should sum to
    categories: List[TimeAllocationCategoryRow]   # all 10 categories, in display_order
    clinical_total_hours: Decimal
    non_clinical_total_hours: Decimal
    allocated_hours: Decimal                # clinical + non-clinical
    hours_variance: Decimal                 # yearly_hours - allocated_hours; 0 = Total Hrs Check passes
    clinical_pct: Decimal                   # derived value this grid would produce, for a live preview


# ── Bulk upsert (PUT /api/physicians/{id}/time-allocations) ────────────────

class TimeAllocationUpsertEntry(BaseModel):
    time_category_id: int
    site_id: Optional[uuid.UUID] = None
    month: int = Field(..., ge=1, le=12)
    hours: Decimal = Field(..., ge=0)
    change_reason: Optional[str] = None


class TimeAllocationBulkUpsert(BaseModel):
    year: int
    allocations: List[TimeAllocationUpsertEntry]


# ── Check worklist (GET /api/time-allocations/check) ────────────────────────
# Same shape as v_time_allocation_check, but computed per-request against the
# requested `year` rather than the view's hardcoded CURRENT_DATE year — see
# the note in routers/time_allocations.py.

class TimeAllocationCheckRow(BaseModel):
    physician_id: uuid.UUID
    last_name: str
    first_name: str
    yearly_hours: int
    allocated_hours: Decimal
    hours_variance: Decimal
