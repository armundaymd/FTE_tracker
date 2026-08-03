import uuid
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models.leave import Leave
from schemas.leave import LeaveCreate, LeaveRead, LeaveUpdate

router = APIRouter()


async def _get_or_404(leave_id: uuid.UUID, db: AsyncSession) -> Leave:
    result = await db.execute(select(Leave).where(Leave.id == leave_id))
    leave = result.scalar_one_or_none()
    if leave is None:
        raise HTTPException(status_code=404, detail="Leave event not found")
    return leave


@router.get("/", response_model=List[LeaveRead])
async def list_leaves(
    physician_id: Optional[uuid.UUID] = Query(None),
    year: Optional[int] = Query(None, ge=2020, le=2100, description="Return leaves that overlap this year"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Leave).order_by(Leave.start_date)

    if physician_id is not None:
        stmt = stmt.where(Leave.physician_id == physician_id)

    if year is not None:
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        # Overlap: leave starts on or before year end AND ends on or after year start
        stmt = stmt.where(Leave.start_date <= year_end).where(Leave.end_date >= year_start)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=LeaveRead, status_code=status.HTTP_201_CREATED)
async def create_leave(payload: LeaveCreate, db: AsyncSession = Depends(get_db)):
    leave = Leave(**payload.model_dump())
    db.add(leave)
    await db.commit()
    await db.refresh(leave)
    return leave


@router.put("/{leave_id}", response_model=LeaveRead)
async def update_leave(
    leave_id: uuid.UUID,
    payload: LeaveUpdate,
    db: AsyncSession = Depends(get_db),
):
    leave = await _get_or_404(leave_id, db)

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(leave, field, value)

    # Re-validate date ordering after partial update
    start = updates.get("start_date", leave.start_date)
    end = updates.get("end_date", leave.end_date)
    if end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be on or after start_date",
        )

    await db.commit()
    await db.refresh(leave)
    return leave


@router.delete("/{leave_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leave(leave_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    leave = await _get_or_404(leave_id, db)
    await db.delete(leave)
    await db.commit()
