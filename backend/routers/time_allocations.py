"""
Top-level (non-physician-scoped) Phase D endpoints:
  GET /api/time-categories
  GET /api/time-allocations/check

(The physician-scoped GET/PUT /api/physicians/{id}/time-allocations
endpoints live in routers/physicians.py, next to the rest of that
resource's sub-endpoints.)
"""

from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models.physician import Physician
from models.time_allocation import TimeAllocation
from models.time_category import TimeCategory
from schemas.time_allocation import TimeAllocationCheckRow, TimeCategoryRead

router = APIRouter()


@router.get("/time-categories", response_model=List[TimeCategoryRead])
async def list_time_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TimeCategory).order_by(TimeCategory.display_order))
    return result.scalars().all()


@router.get("/time-allocations/check", response_model=List[TimeAllocationCheckRow])
async def check_time_allocations(
    year: int = Query(..., ge=2020, le=2100),
    db: AsyncSession = Depends(get_db),
):
    """
    Active physicians whose time_allocations hours for `year` don't sum to
    their yearly_hours — the "Total Hrs Check" worklist.

    NOTE: this does NOT query the v_time_allocation_check view. That view
    (schema.sql) hardcodes EXTRACT(YEAR FROM CURRENT_DATE) in its join
    condition, so it can only ever check the current calendar year — it
    can't take an arbitrary `year` parameter the way this endpoint's own
    signature (and ROADMAP_PHASE_D.md's) does. This query mirrors the
    view's exact logic, parameterized by `year` instead. The view itself is
    left as-is in schema.sql for ad-hoc "what does today look like" SQL —
    just not used by this endpoint for any year other than the current one.
    """
    stmt = (
        select(
            Physician.id.label("physician_id"),
            Physician.last_name,
            Physician.first_name,
            Physician.yearly_hours,
        )
        .where(Physician.is_active == True)
        .order_by(Physician.last_name, Physician.first_name)
    )
    physicians = (await db.execute(stmt)).all()

    allocations_stmt = (
        select(TimeAllocation.physician_id, TimeAllocation.hours)
        .where(TimeAllocation.year == year)
    )
    allocated_by_physician: dict = {}
    for physician_id, hours in (await db.execute(allocations_stmt)).all():
        allocated_by_physician[physician_id] = allocated_by_physician.get(physician_id, Decimal("0")) + hours

    rows: List[TimeAllocationCheckRow] = []
    for p in physicians:
        allocated_hours = allocated_by_physician.get(p.physician_id, Decimal("0"))
        yearly_hours_decimal = Decimal(p.yearly_hours)
        if allocated_hours != yearly_hours_decimal:
            rows.append(TimeAllocationCheckRow(
                physician_id=p.physician_id,
                last_name=p.last_name,
                first_name=p.first_name,
                yearly_hours=p.yearly_hours,
                allocated_hours=allocated_hours,
                hours_variance=yearly_hours_decimal - allocated_hours,
            ))

    return rows
