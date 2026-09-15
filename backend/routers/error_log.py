from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models.error_log import ErrorLog
from schemas.error_log import ErrorLogRead

router = APIRouter()


@router.get("/", response_model=List[ErrorLogRead])
async def list_error_log(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ErrorLog).order_by(ErrorLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return result.scalars().all()
