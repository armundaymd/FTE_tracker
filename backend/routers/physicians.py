import uuid
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db import get_db
from models.physician import PhysicianRole, ProviderType, RoleType, Physician, SiteAssignment
from schemas.physician import (
    PhysicianCreate,
    PhysicianRead,
    PhysicianRoleCreate,
    PhysicianRoleRead,
    PhysicianUpdate,
    ProviderTypeRead,
    RoleTypeRead,
    SiteAssignmentCreate,
    SiteAssignmentRead,
    SiteAssignmentUpdate,
)

router = APIRouter()


# ── Shared helpers ─────────────────────────────────────────────────────────

async def _load_physician(physician_id: uuid.UUID, db: AsyncSession) -> Optional[Physician]:
    result = await db.execute(
        select(Physician)
        .where(Physician.id == physician_id)
        .options(
            selectinload(Physician.provider_type),
            selectinload(Physician.assignments),
            selectinload(Physician.roles).selectinload(PhysicianRole.role_type),
        )
    )
    return result.scalar_one_or_none()


async def _get_or_404(physician_id: uuid.UUID, db: AsyncSession) -> Physician:
    physician = await _load_physician(physician_id, db)
    if physician is None:
        raise HTTPException(status_code=404, detail="Physician not found")
    return physician


async def _sync_total_fte(physician_id: uuid.UUID, db: AsyncSession) -> None:
    """Recompute and persist total_fte from active site assignments."""
    result = await db.execute(
        select(SiteAssignment)
        .where(SiteAssignment.physician_id == physician_id)
        .where(SiteAssignment.end_date.is_(None))
    )
    total = sum(float(a.fte_fraction) for a in result.scalars().all())
    result2 = await db.execute(select(Physician).where(Physician.id == physician_id))
    physician = result2.scalar_one()
    physician.total_fte = Decimal(str(round(total, 4)))


# ── Lookup tables ──────────────────────────────────────────────────────────
# Must be registered before /{physician_id} to avoid routing conflict.

@router.get("/lookup-tables")
async def get_lookup_tables(db: AsyncSession = Depends(get_db)):
    """Return provider_types and role_types for form dropdowns."""
    pt_result = await db.execute(select(ProviderType).order_by(ProviderType.display_order))
    rt_result = await db.execute(select(RoleType).order_by(RoleType.display_order))
    return {
        "provider_types": [ProviderTypeRead.model_validate(r) for r in pt_result.scalars().all()],
        "role_types": [RoleTypeRead.model_validate(r) for r in rt_result.scalars().all()],
    }


# ── Physician CRUD ─────────────────────────────────────────────────────────

@router.get("/", response_model=List[PhysicianRead])
async def list_physicians(
    active: Optional[bool] = Query(True, description="Filter by is_active (omit for all)"),
    type: Optional[str] = Query(None, description="Provider type name, e.g. MD, NP, PA"),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Physician)
        .options(
            selectinload(Physician.provider_type),
            selectinload(Physician.assignments),
            selectinload(Physician.roles).selectinload(PhysicianRole.role_type),
        )
        .order_by(Physician.last_name, Physician.first_name)
    )
    if active is not None:
        stmt = stmt.where(Physician.is_active == active)
    if type is not None:
        stmt = stmt.join(ProviderType, Physician.provider_type_id == ProviderType.id)
        stmt = stmt.where(ProviderType.name == type)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=PhysicianRead, status_code=status.HTTP_201_CREATED)
async def create_physician(payload: PhysicianCreate, db: AsyncSession = Depends(get_db)):
    physician = Physician(**payload.model_dump(exclude={"assignments", "roles"}))
    db.add(physician)
    await db.flush()  # materialise physician.id

    for a in payload.assignments:
        db.add(SiteAssignment(physician_id=physician.id, **a.model_dump()))

    for r in payload.roles:
        db.add(PhysicianRole(physician_id=physician.id, **r.model_dump()))

    # Compute total_fte from the assignments we just staged
    total_fte = sum(float(a.fte_fraction) for a in payload.assignments)
    physician.total_fte = Decimal(str(round(total_fte, 4)))

    await db.commit()
    return await _get_or_404(physician.id, db)


@router.get("/{physician_id}", response_model=PhysicianRead)
async def get_physician(physician_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _get_or_404(physician_id, db)


@router.put("/{physician_id}", response_model=PhysicianRead)
async def update_physician(
    physician_id: uuid.UUID,
    payload: PhysicianUpdate,
    db: AsyncSession = Depends(get_db),
):
    physician = await _get_or_404(physician_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(physician, field, value)
    await db.commit()
    return await _get_or_404(physician_id, db)


@router.delete("/{physician_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_physician(physician_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    physician = await _get_or_404(physician_id, db)
    physician.is_active = False
    await db.commit()


# ── Site assignments sub-resource ──────────────────────────────────────────

@router.post(
    "/{physician_id}/assignments",
    response_model=SiteAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_assignment(
    physician_id: uuid.UUID,
    payload: SiteAssignmentCreate,
    db: AsyncSession = Depends(get_db),
):
    await _get_or_404(physician_id, db)  # 404 guard

    assignment = SiteAssignment(physician_id=physician_id, **payload.model_dump())
    db.add(assignment)
    await db.flush()
    await _sync_total_fte(physician_id, db)
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.put(
    "/{physician_id}/assignments/{assignment_id}",
    response_model=SiteAssignmentRead,
)
async def update_assignment(
    physician_id: uuid.UUID,
    assignment_id: uuid.UUID,
    payload: SiteAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SiteAssignment)
        .where(SiteAssignment.id == assignment_id)
        .where(SiteAssignment.physician_id == physician_id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(assignment, field, value)

    await db.flush()
    await _sync_total_fte(physician_id, db)
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.delete(
    "/{physician_id}/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_assignment(
    physician_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SiteAssignment)
        .where(SiteAssignment.id == assignment_id)
        .where(SiteAssignment.physician_id == physician_id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    await db.delete(assignment)
    await db.flush()
    await _sync_total_fte(physician_id, db)
    await db.commit()


# ── Physician roles sub-resource ───────────────────────────────────────────

@router.post(
    "/{physician_id}/roles",
    response_model=PhysicianRoleRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_role(
    physician_id: uuid.UUID,
    payload: PhysicianRoleCreate,
    db: AsyncSession = Depends(get_db),
):
    await _get_or_404(physician_id, db)  # 404 guard

    role = PhysicianRole(physician_id=physician_id, **payload.model_dump())
    db.add(role)
    await db.commit()
    await db.refresh(role)

    # Reload with role_type relationship
    result = await db.execute(
        select(PhysicianRole)
        .where(PhysicianRole.id == role.id)
        .options(selectinload(PhysicianRole.role_type))
    )
    return result.scalar_one()


@router.delete(
    "/{physician_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_role(
    physician_id: uuid.UUID,
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PhysicianRole)
        .where(PhysicianRole.id == role_id)
        .where(PhysicianRole.physician_id == physician_id)
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")

    await db.delete(role)
    await db.commit()
