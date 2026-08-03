import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models.demand import MonthlyDemand
from schemas.demand import MonthlyDemandCreate, MonthlyDemandRead

router = APIRouter()


@router.get("/", response_model=List[MonthlyDemandRead])
async def list_demand(
    year: int = Query(..., ge=2020, le=2100),
    site_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MonthlyDemand)
        .where(MonthlyDemand.year == year)
        .order_by(MonthlyDemand.site_id, MonthlyDemand.month)
    )
    if site_id is not None:
        stmt = stmt.where(MonthlyDemand.site_id == site_id)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.put("/", response_model=MonthlyDemandRead, status_code=status.HTTP_200_OK)
async def upsert_demand(payload: MonthlyDemandCreate, db: AsyncSession = Depends(get_db)):
    """
    Insert or update a single site+year+month demand row.
    Uses the uq_monthly_demand unique constraint (site_id, year, month).
    """
    result = await db.execute(
        select(MonthlyDemand)
        .where(MonthlyDemand.site_id == payload.site_id)
        .where(MonthlyDemand.year == payload.year)
        .where(MonthlyDemand.month == payload.month)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = MonthlyDemand(
            site_id=payload.site_id,
            year=payload.year,
            month=payload.month,
            hours_required=payload.hours_required,
            notes=payload.notes,
        )
        db.add(row)
    else:
        row.hours_required = payload.hours_required
        row.notes = payload.notes
        row.updated_at = datetime.now(tz=timezone.utc)

    await db.commit()
    await db.refresh(row)
    return row
