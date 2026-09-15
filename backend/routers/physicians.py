import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth.dependencies import CurrentUser, get_current_user
from audit.logger import log_audit, snapshot
from db import get_db
from models.leave import Leave
from models.physician import PhysicianRole, ProviderType, RoleType, Physician, SiteAssignment
from models.site import Site
from models.time_allocation import TimeAllocation
from models.time_category import TimeCategory
from schemas.fte_history import FTEHistoryEntry, FTEHistoryResponse
from schemas.leave import LeaveRead
from schemas.physician import (
    PhysicianCreate,
    PhysicianRead,
    PhysicianRoleCreate,
    PhysicianRoleRead,
    PhysicianRoleUpdate,
    PhysicianUpdate,
    ProviderTypeRead,
    RoleTypeRead,
    SiteAssignmentCreate,
    SiteAssignmentRead,
    SiteAssignmentUpdate,
)
from schemas.time_allocation import (
    TimeAllocationBulkUpsert,
    TimeAllocationCategoryRow,
    TimeAllocationCell,
    TimeAllocationGrid,
    TimeAllocationRead,
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


def _role_credit_desc(role: PhysicianRole) -> Optional[str]:
    if role.pct_credit:
        return f"{float(role.pct_credit) * 100:.0f}% credit"
    if role.hours_credit:
        return f"{role.hours_credit}h credit"
    return None


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


async def _sync_time_allocation_derived(physician_id: uuid.UUID, year: int, db: AsyncSession) -> None:
    """
    Recompute and persist clinical_pct and needs_time_allocation_config from
    this physician's time_allocations rows for `year` (Phase D).

    clinical_pct = SUM(hours WHERE is_clinical) / SUM(hours). If SUM(hours)
    is zero (no rows yet, or all-zero rows), clinical_pct is left
    unchanged — avoids dividing by zero and matches the additive-migration
    fallback: a physician with no allocations keeps whatever clinical_pct
    they had before.
    """
    result = await db.execute(
        select(TimeAllocation.hours, TimeCategory.is_clinical)
        .join(TimeCategory, TimeAllocation.time_category_id == TimeCategory.id)
        .where(TimeAllocation.physician_id == physician_id)
        .where(TimeAllocation.year == year)
    )
    rows = result.all()

    total_hours = sum((r.hours for r in rows), Decimal("0"))
    clinical_hours = sum((r.hours for r in rows if r.is_clinical), Decimal("0"))

    result2 = await db.execute(select(Physician).where(Physician.id == physician_id))
    physician = result2.scalar_one()

    if total_hours > 0:
        physician.clinical_pct = (clinical_hours / total_hours).quantize(Decimal("0.0001"))

    physician.needs_time_allocation_config = total_hours != Decimal(physician.yearly_hours)


async def _build_time_allocation_grid(physician: Physician, year: int, db: AsyncSession) -> TimeAllocationGrid:
    """Assembles the full category x month grid for one physician/year — always
    all 10 categories with 12 cells each, zero-filled for months with no row,
    so the frontend never has to special-case a not-yet-configured physician."""
    categories_result = await db.execute(select(TimeCategory).order_by(TimeCategory.display_order))
    categories = categories_result.scalars().all()

    allocations_result = await db.execute(
        select(TimeAllocation)
        .where(TimeAllocation.physician_id == physician.id)
        .where(TimeAllocation.year == year)
    )
    allocations = allocations_result.scalars().all()

    allocations_by_category: dict = {}
    for a in allocations:
        allocations_by_category.setdefault(a.time_category_id, []).append(a)

    category_rows: List[TimeAllocationCategoryRow] = []
    clinical_total = Decimal("0")
    non_clinical_total = Decimal("0")

    for cat in categories:
        cat_allocations = allocations_by_category.get(cat.id, [])
        by_month: dict = {}
        for a in cat_allocations:
            by_month.setdefault(a.month, []).append(a)

        cells: List[TimeAllocationCell] = []
        for month in range(1, 13):
            month_rows = by_month.get(month)
            if month_rows:
                for a in month_rows:
                    cells.append(TimeAllocationCell(
                        site_id=a.site_id, month=month, hours=a.hours, change_reason=a.change_reason,
                    ))
            else:
                cells.append(TimeAllocationCell(site_id=None, month=month, hours=Decimal("0"), change_reason=None))

        category_total = sum((a.hours for a in cat_allocations), Decimal("0"))
        if cat.is_clinical:
            clinical_total += category_total
        else:
            non_clinical_total += category_total

        category_rows.append(TimeAllocationCategoryRow(
            time_category_id=cat.id, category_name=cat.name, is_clinical=cat.is_clinical,
            cells=cells, category_total_hours=category_total,
        ))

    allocated_hours = clinical_total + non_clinical_total
    hours_variance = Decimal(physician.yearly_hours) - allocated_hours
    clinical_pct = (
        (clinical_total / allocated_hours).quantize(Decimal("0.0001"))
        if allocated_hours > 0
        else physician.clinical_pct
    )

    return TimeAllocationGrid(
        physician_id=physician.id,
        year=year,
        yearly_hours=physician.yearly_hours,
        categories=category_rows,
        clinical_total_hours=clinical_total,
        non_clinical_total_hours=non_clinical_total,
        allocated_hours=allocated_hours,
        hours_variance=hours_variance,
        clinical_pct=clinical_pct,
    )


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
    site_id: Optional[uuid.UUID] = Query(None, description="Only physicians with a current (active) assignment at this site"),
    provider_type_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None, description="Filter by is_active (omit for all)"),
    is_core_faculty: Optional[bool] = Query(None),
    needs_fte_config: Optional[bool] = Query(None),
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
    if is_active is not None:
        stmt = stmt.where(Physician.is_active == is_active)
    if provider_type_id is not None:
        stmt = stmt.where(Physician.provider_type_id == provider_type_id)
    if is_core_faculty is not None:
        stmt = stmt.where(Physician.is_core_faculty == is_core_faculty)
    if needs_fte_config is not None:
        stmt = stmt.where(Physician.needs_fte_config == needs_fte_config)
    if site_id is not None:
        # "has an active (currently open) assignment at this site"
        stmt = (
            stmt.join(SiteAssignment, SiteAssignment.physician_id == Physician.id)
            .where(SiteAssignment.site_id == site_id)
            .where(SiteAssignment.end_date.is_(None))
            .distinct()
        )

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=PhysicianRead, status_code=status.HTTP_201_CREATED)
async def create_physician(
    payload: PhysicianCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
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

    result = await _get_or_404(physician.id, db)
    await log_audit(
        db, current_user, "INSERT", "physicians", physician.id,
        new_values=snapshot(PhysicianRead, result),
    )
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
    current_user: CurrentUser = Depends(get_current_user),
):
    physician = await _get_or_404(physician_id, db)
    updates = payload.model_dump(exclude_unset=True)

    if "clinical_pct" in updates:
        # Phase D: once a physician has any time_allocations rows for the
        # current year, clinical_pct is derived from them — reject a manual
        # write rather than silently clobbering the derived value.
        current_year = date.today().year
        result = await db.execute(
            select(TimeAllocation.id)
            .where(TimeAllocation.physician_id == physician_id)
            .where(TimeAllocation.year == current_year)
            .limit(1)
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="clinical_pct is derived from time_allocations for this physician and cannot be set directly. Edit their time allocations instead.",
            )

    old_values = snapshot(PhysicianRead, physician)
    for field, value in updates.items():
        setattr(physician, field, value)
    updated = await _get_or_404(physician_id, db)
    await log_audit(
        db, current_user, "UPDATE", "physicians", physician_id,
        old_values=old_values, new_values=snapshot(PhysicianRead, updated),
    )
    await db.commit()
    return await _get_or_404(physician_id, db)


@router.delete("/{physician_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_physician(
    physician_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    physician = await _get_or_404(physician_id, db)
    old_values = snapshot(PhysicianRead, physician)
    physician.is_active = False
    await log_audit(db, current_user, "DELETE", "physicians", physician_id, old_values=old_values)
    await db.commit()


# ── FTE history ──────────────────────────────────────────────────────────────

@router.get("/{physician_id}/fte-history", response_model=FTEHistoryResponse)
async def get_fte_history(physician_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Merged, chronological timeline of everything that affects a physician's
    FTE: the full site_assignments history, the full physician_roles
    history, and their leave events — one consistent shape regardless of
    source table, sorted by date.
    """
    await _get_or_404(physician_id, db)  # 404 guard

    assignments_result = await db.execute(
        select(SiteAssignment, Site)
        .join(Site, SiteAssignment.site_id == Site.id)
        .where(SiteAssignment.physician_id == physician_id)
        .order_by(SiteAssignment.effective_date)
    )
    assignment_rows = assignments_result.all()

    roles_result = await db.execute(
        select(PhysicianRole)
        .where(PhysicianRole.physician_id == physician_id)
        .options(selectinload(PhysicianRole.role_type))
        .order_by(PhysicianRole.effective_date)
    )
    role_rows = roles_result.scalars().all()

    leaves_result = await db.execute(
        select(Leave)
        .where(Leave.physician_id == physician_id)
        .order_by(Leave.start_date)
    )
    leave_rows = leaves_result.scalars().all()

    entries: List[FTEHistoryEntry] = []

    # ── Assignments: describe each row relative to the prior row at that site
    previous_fte_by_site: dict = {}
    for sa, site in assignment_rows:
        site_label = site.short_name or site.name
        previous_fte = previous_fte_by_site.get(sa.site_id)
        if previous_fte is None:
            description = f"Started assignment at {site_label} at {sa.fte_fraction} FTE"
        elif previous_fte != sa.fte_fraction:
            description = f"{site_label} assignment changed from {previous_fte} to {sa.fte_fraction} FTE"
        else:
            description = f"{site_label} assignment updated"
        if sa.end_date is not None:
            description += f" (ended {sa.end_date.isoformat()})"
        previous_fte_by_site[sa.site_id] = sa.fte_fraction

        entries.append(FTEHistoryEntry(
            date=sa.effective_date,
            type="assignment",
            description=description,
            change_reason=sa.change_reason,
            detail=snapshot(SiteAssignmentRead, sa),
        ))

    # ── Roles: describe each row relative to the prior row for that role
    previous_role_by_key: dict = {}
    for role in role_rows:
        role_name = role.role_type.name if role.role_type else (role.custom_title or "Role")
        credit_desc = _role_credit_desc(role)
        role_key = (role.role_type_id, role.custom_title)
        if role_key not in previous_role_by_key:
            description = f"Added role: {role_name}" + (f" ({credit_desc})" if credit_desc else "")
        else:
            description = f"{role_name} credit changed" + (f" to {credit_desc}" if credit_desc else "")
        if role.end_date is not None:
            description += f" (ended {role.end_date.isoformat()})"
        previous_role_by_key[role_key] = role

        entries.append(FTEHistoryEntry(
            date=role.effective_date,
            type="role",
            description=description,
            change_reason=role.change_reason,
            detail=snapshot(PhysicianRoleRead, role),
        ))

    # ── Leaves
    for leave in leave_rows:
        kind = "partial " if leave.is_partial else ""
        entries.append(FTEHistoryEntry(
            date=leave.start_date,
            type="leave",
            description=f"Started {kind}{leave.leave_type} leave",
            change_reason=None,
            detail=snapshot(LeaveRead, leave),
        ))

    entries.sort(key=lambda e: e.date)

    return FTEHistoryResponse(physician_id=physician_id, entries=entries)


# ── Time allocations (Phase D) ────────────────────────────────────────────────

@router.get("/{physician_id}/time-allocations", response_model=TimeAllocationGrid)
async def get_time_allocations(
    physician_id: uuid.UUID,
    year: int = Query(..., ge=2020, le=2100),
    db: AsyncSession = Depends(get_db),
):
    """
    Full category x month grid for one physician/year. If the physician has
    no rows for this year, returns an all-zero grid rather than 404 — the
    frontend renders that as "not yet configured."
    """
    physician = await _get_or_404(physician_id, db)
    return await _build_time_allocation_grid(physician, year, db)


@router.put("/{physician_id}/time-allocations", response_model=TimeAllocationGrid)
async def upsert_time_allocations(
    physician_id: uuid.UUID,
    payload: TimeAllocationBulkUpsert,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Bulk-upserts every entry in payload.allocations (matched on the
    physician_id/site_id/time_category_id/year/month unique constraint),
    then — in the same transaction — recomputes and persists this
    physician's clinical_pct and needs_time_allocation_config from the
    resulting rows. capacity.py reads physicians.clinical_pct as a plain
    column with no caching, so this synchronous recompute is what keeps
    /api/capacity correct without any change to that endpoint.
    """
    physician = await _get_or_404(physician_id, db)
    old_physician_values = snapshot(PhysicianRead, physician)

    for entry in payload.allocations:
        result = await db.execute(
            select(TimeAllocation)
            .where(TimeAllocation.physician_id == physician_id)
            .where(TimeAllocation.site_id == entry.site_id)
            .where(TimeAllocation.time_category_id == entry.time_category_id)
            .where(TimeAllocation.year == payload.year)
            .where(TimeAllocation.month == entry.month)
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = TimeAllocation(
                physician_id=physician_id,
                site_id=entry.site_id,
                time_category_id=entry.time_category_id,
                year=payload.year,
                month=entry.month,
                hours=entry.hours,
                change_reason=entry.change_reason,
            )
            db.add(row)
            await db.flush()
            await log_audit(
                db, current_user, "INSERT", "time_allocations", row.id,
                new_values=snapshot(TimeAllocationRead, row),
            )
        else:
            old_row_values = snapshot(TimeAllocationRead, row)
            row.hours = entry.hours
            row.change_reason = entry.change_reason
            await db.flush()
            await log_audit(
                db, current_user, "UPDATE", "time_allocations", row.id,
                old_values=old_row_values, new_values=snapshot(TimeAllocationRead, row),
            )

    await _sync_time_allocation_derived(physician_id, payload.year, db)

    updated_physician = await _get_or_404(physician_id, db)
    await log_audit(
        db, current_user, "UPDATE", "physicians", physician_id,
        old_values=old_physician_values, new_values=snapshot(PhysicianRead, updated_physician),
    )

    await db.commit()

    refreshed = await _get_or_404(physician_id, db)
    return await _build_time_allocation_grid(refreshed, payload.year, db)


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
    current_user: CurrentUser = Depends(get_current_user),
):
    await _get_or_404(physician_id, db)  # 404 guard

    assignment = SiteAssignment(physician_id=physician_id, **payload.model_dump())
    db.add(assignment)
    await db.flush()
    await _sync_total_fte(physician_id, db)
    await log_audit(
        db, current_user, "INSERT", "site_assignments", assignment.id,
        new_values=snapshot(SiteAssignmentRead, assignment),
    )
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
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(SiteAssignment)
        .where(SiteAssignment.id == assignment_id)
        .where(SiteAssignment.physician_id == physician_id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    updates = payload.model_dump(exclude_unset=True)
    old_values = snapshot(SiteAssignmentRead, assignment)

    is_substantive = (
        ("fte_fraction" in updates and updates["fte_fraction"] != assignment.fte_fraction)
        or ("site_id" in updates and updates["site_id"] != assignment.site_id)
    )

    if is_substantive:
        if assignment.end_date is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This assignment has already ended — add a new assignment instead of changing its FTE.",
            )

        new_effective_date = updates.get("effective_date") or date.today()
        old_end_date = new_effective_date - timedelta(days=1)
        if old_end_date < assignment.effective_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New effective date must be after this assignment's current effective date.",
            )

        # Close the existing row as of the day before the change, then open a
        # new one — this is what makes site_assignments a real history instead
        # of overwriting the FTE in place.
        assignment.end_date = old_end_date
        await db.flush()

        new_assignment = SiteAssignment(
            physician_id=physician_id,
            site_id=updates.get("site_id", assignment.site_id),
            fte_fraction=updates.get("fte_fraction", assignment.fte_fraction),
            effective_date=new_effective_date,
            end_date=None,
            notes=updates.get("notes", assignment.notes),
            change_reason=updates.get("change_reason"),
        )
        db.add(new_assignment)
        await db.flush()
        await _sync_total_fte(physician_id, db)

        await log_audit(
            db, current_user, "UPDATE", "site_assignments", assignment_id,
            old_values=old_values, new_values=snapshot(SiteAssignmentRead, assignment),
        )
        await log_audit(
            db, current_user, "INSERT", "site_assignments", new_assignment.id,
            new_values=snapshot(SiteAssignmentRead, new_assignment),
        )
        await db.commit()
        await db.refresh(new_assignment)
        return new_assignment

    # Non-substantive: notes/change_reason, or a direct end_date to close out
    # the assignment with no replacement — safe to edit in place.
    for field in ("notes", "change_reason", "end_date"):
        if field in updates:
            setattr(assignment, field, updates[field])

    await db.flush()
    await _sync_total_fte(physician_id, db)
    await log_audit(
        db, current_user, "UPDATE", "site_assignments", assignment_id,
        old_values=old_values, new_values=snapshot(SiteAssignmentRead, assignment),
    )
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
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(SiteAssignment)
        .where(SiteAssignment.id == assignment_id)
        .where(SiteAssignment.physician_id == physician_id)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    old_values = snapshot(SiteAssignmentRead, assignment)
    await db.delete(assignment)
    await db.flush()
    await _sync_total_fte(physician_id, db)
    await log_audit(db, current_user, "DELETE", "site_assignments", assignment_id, old_values=old_values)
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
    current_user: CurrentUser = Depends(get_current_user),
):
    await _get_or_404(physician_id, db)  # 404 guard

    role = PhysicianRole(physician_id=physician_id, **payload.model_dump())
    db.add(role)
    await db.flush()

    # Reload with role_type relationship
    result = await db.execute(
        select(PhysicianRole)
        .where(PhysicianRole.id == role.id)
        .options(selectinload(PhysicianRole.role_type))
    )
    loaded_role = result.scalar_one()
    await log_audit(
        db, current_user, "INSERT", "physician_roles", role.id,
        new_values=snapshot(PhysicianRoleRead, loaded_role),
    )
    await db.commit()
    await db.refresh(role)

    result = await db.execute(
        select(PhysicianRole)
        .where(PhysicianRole.id == role.id)
        .options(selectinload(PhysicianRole.role_type))
    )
    return result.scalar_one()


@router.put(
    "/{physician_id}/roles/{role_id}",
    response_model=PhysicianRoleRead,
)
async def update_role(
    physician_id: uuid.UUID,
    role_id: uuid.UUID,
    payload: PhysicianRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(PhysicianRole)
        .where(PhysicianRole.id == role_id)
        .where(PhysicianRole.physician_id == physician_id)
        .options(selectinload(PhysicianRole.role_type))
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")

    updates = payload.model_dump(exclude_unset=True)
    old_values = snapshot(PhysicianRoleRead, role)

    is_substantive = (
        ("hours_credit" in updates and updates["hours_credit"] != role.hours_credit)
        or ("pct_credit" in updates and updates["pct_credit"] != role.pct_credit)
    )

    if is_substantive:
        if role.end_date is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="This role has already ended — add a new role instead of changing its credit.",
            )

        new_effective_date = updates.get("effective_date") or date.today()
        old_end_date = new_effective_date - timedelta(days=1)
        if old_end_date < role.effective_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="New effective date must be after this role's current effective date.",
            )

        role.end_date = old_end_date
        await db.flush()

        new_role = PhysicianRole(
            physician_id=physician_id,
            role_type_id=updates.get("role_type_id", role.role_type_id),
            custom_title=updates.get("custom_title", role.custom_title),
            hours_credit=updates.get("hours_credit", role.hours_credit),
            pct_credit=updates.get("pct_credit", role.pct_credit),
            effective_date=new_effective_date,
            end_date=None,
            notes=updates.get("notes", role.notes),
            change_reason=updates.get("change_reason"),
        )
        db.add(new_role)
        await db.flush()

        await log_audit(
            db, current_user, "UPDATE", "physician_roles", role_id,
            old_values=old_values, new_values=snapshot(PhysicianRoleRead, role),
        )

        result = await db.execute(
            select(PhysicianRole)
            .where(PhysicianRole.id == new_role.id)
            .options(selectinload(PhysicianRole.role_type))
        )
        loaded_new_role = result.scalar_one()
        await log_audit(
            db, current_user, "INSERT", "physician_roles", new_role.id,
            new_values=snapshot(PhysicianRoleRead, loaded_new_role),
        )
        await db.commit()
        return loaded_new_role

    # Non-substantive: role_type/custom_title/notes/change_reason, or a direct
    # end_date to close out the role with no replacement — safe in place.
    for field in ("role_type_id", "custom_title", "notes", "change_reason", "end_date"):
        if field in updates:
            setattr(role, field, updates[field])

    await db.flush()
    await log_audit(
        db, current_user, "UPDATE", "physician_roles", role_id,
        old_values=old_values, new_values=snapshot(PhysicianRoleRead, role),
    )
    await db.commit()

    result = await db.execute(
        select(PhysicianRole)
        .where(PhysicianRole.id == role_id)
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
    current_user: CurrentUser = Depends(get_current_user),
):
    result = await db.execute(
        select(PhysicianRole)
        .where(PhysicianRole.id == role_id)
        .where(PhysicianRole.physician_id == physician_id)
        .options(selectinload(PhysicianRole.role_type))
    )
    role = result.scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")

    old_values = snapshot(PhysicianRoleRead, role)
    await db.delete(role)
    await log_audit(db, current_user, "DELETE", "physician_roles", role_id, old_values=old_values)
    await db.commit()
