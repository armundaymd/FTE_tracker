import uuid
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models.audit_log import AuditLog
from schemas.audit_log import AuditLogRead

router = APIRouter()


@router.get("/", response_model=List[AuditLogRead])
async def list_audit_log(
    table_name: Optional[str] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    action: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None, description="Include entries created on or after this date"),
    end_date: Optional[date] = Query(None, description="Include entries created on or before this date"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())

    if table_name is not None:
        stmt = stmt.where(AuditLog.table_name == table_name)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if start_date is not None:
        stmt = stmt.where(AuditLog.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(AuditLog.created_at < end_date + timedelta(days=1))

    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    return result.scalars().all()
