"""
Capacity calculation endpoint.

Algorithm (mirrors the prototype's useMemo logic in App.jsx):

For each (site, month):
  For each active physician assigned to that site:
    base_monthly_hours = (yearly_hours / 12) * fte_fraction

    # Sum leave reductions across all overlapping leaves
    total_reduction = 0.0
    for each leave overlapping this month:
        overlap_days / days_in_month → overlap_fraction
        if is_partial and fte_during_leave is set:
            reduction = overlap_fraction * (1 - fte_during_leave)
        else:
            reduction = overlap_fraction   # fully out during overlap
        total_reduction = min(1.0, total_reduction + reduction)

    available_fraction = 1.0 - total_reduction
    available_hours   += base_monthly_hours * available_fraction
    available_fte     += fte_fraction * available_fraction
    clinical_hours    += available_hours * clinical_pct
    non_clinical_hours+= available_hours * (1 - clinical_pct)

  required_hours = monthly_demand[site][month]
  required_fte   = required_hours / avg_monthly_hours_across_all_physicians
  hours_gap      = available_hours - required_hours
  fte_gap        = available_fte   - required_fte
"""

import calendar
import uuid
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models.demand import MonthlyDemand
from models.leave import Leave
from models.physician import Physician, SiteAssignment
from models.site import Site
from schemas.capacity import CapacityResponse, SiteMonthCapacity

router = APIRouter()


# ── Leave overlap helpers ──────────────────────────────────────────────────

def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _leave_reduction(
    leave_start: date,
    leave_end: date,
    fte_during_leave: Optional[Decimal],
    year: int,
    month: int,
) -> float:
    """
    Fraction of monthly availability LOST due to this leave.

    Returns 0.0 if the leave doesn't touch the month.
    Returns a value in [0, 1] representing the proportional reduction.

    For a partial leave (fte_during_leave set), the physician is still
    working at that FTE level, so only the remainder is lost:
        reduction = overlap_fraction * (1 - fte_during_leave)
    For a full leave (fte_during_leave is None), the physician is fully out:
        reduction = overlap_fraction
    """
    dim = _days_in_month(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, dim)

    if leave_start > month_end or leave_end < month_start:
        return 0.0

    overlap_start = max(leave_start, month_start)
    overlap_end = min(leave_end, month_end)
    overlap_days = (overlap_end - overlap_start).days + 1
    overlap_fraction = overlap_days / dim

    if fte_during_leave is not None:
        return overlap_fraction * (1.0 - float(fte_during_leave))
    return overlap_fraction


# ── Endpoint ───────────────────────────────────────────────────────────────

@router.get("/", response_model=CapacityResponse)
async def get_capacity(
    year: int = Query(..., ge=2020, le=2100, description="Year to calculate capacity for"),
    site_id: Optional[uuid.UUID] = Query(None, description="Filter to a single site"),
    db: AsyncSession = Depends(get_db),
):
    # ── 1. Active sites ──────────────────────────────────────────────────────
    sites_stmt = select(Site).where(Site.active == True)
    if site_id is not None:
        sites_stmt = sites_stmt.where(Site.id == site_id)
    sites_result = await db.execute(sites_stmt.order_by(Site.name))
    sites = sites_result.scalars().all()

    if not sites:
        return CapacityResponse(year=year, site_id=site_id, rows=[])

    site_ids = [s.id for s in sites]
    site_map = {s.id: s for s in sites}

    # ── 2. Active site assignments (end_date IS NULL, physician is_active) ───
    assignments_stmt = (
        select(SiteAssignment, Physician)
        .join(Physician, SiteAssignment.physician_id == Physician.id)
        .where(SiteAssignment.end_date.is_(None))
        .where(SiteAssignment.site_id.in_(site_ids))
        .where(Physician.is_active == True)
    )
    assignments_result = await db.execute(assignments_stmt)
    assignment_rows = assignments_result.all()

    # Per-site: list of (fte_fraction, yearly_hours, clinical_pct, physician_id)
    AssignmentTuple = Tuple[float, int, float, uuid.UUID]
    assignments_by_site: Dict[uuid.UUID, List[AssignmentTuple]] = {s.id: [] for s in sites}

    physician_map: Dict[uuid.UUID, Physician] = {}
    physician_ids: Set[uuid.UUID] = set()

    for sa, ph in assignment_rows:
        assignments_by_site[sa.site_id].append(
            (float(sa.fte_fraction), ph.yearly_hours, float(ph.clinical_pct), ph.id)
        )
        physician_map[ph.id] = ph
        physician_ids.add(ph.id)

    # ── 3. Leaves that overlap the requested year ────────────────────────────
    leaves_by_physician: Dict[uuid.UUID, List[Leave]] = {}

    if physician_ids:
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        leaves_stmt = (
            select(Leave)
            .where(Leave.physician_id.in_(list(physician_ids)))
            .where(Leave.start_date <= year_end)
            .where(Leave.end_date >= year_start)
        )
        for leave in (await db.execute(leaves_stmt)).scalars().all():
            leaves_by_physician.setdefault(leave.physician_id, []).append(leave)

    # ── 4. Monthly demand for these sites ────────────────────────────────────
    demand_stmt = (
        select(MonthlyDemand)
        .where(MonthlyDemand.year == year)
        .where(MonthlyDemand.site_id.in_(site_ids))
    )
    demand_by_site_month: Dict[Tuple[uuid.UUID, int], float] = {}
    for row in (await db.execute(demand_stmt)).scalars().all():
        demand_by_site_month[(row.site_id, row.month)] = float(row.hours_required)

    # ── 5. Average monthly hours — FTE denominator (mirrors prototype) ────────
    # avg(yearlyHours / 12) across all physicians with active assignments
    avg_monthly_hours: float = (
        sum(ph.yearly_hours / 12 for ph in physician_map.values()) / len(physician_map)
        if physician_map
        else 120.0
    )

    # ── 6. Build capacity rows ───────────────────────────────────────────────
    rows: List[SiteMonthCapacity] = []

    for site in sorted(sites, key=lambda s: s.name):
        for month in range(1, 13):
            avail_hours = 0.0
            avail_fte = 0.0
            clinical_hours = 0.0
            non_clinical_hours = 0.0

            for fte_fraction, yearly_hours, clinical_pct, ph_id in assignments_by_site[site.id]:
                base_monthly = (yearly_hours / 12) * fte_fraction

                # Accumulate reduction from all leaves for this physician this month
                total_reduction = 0.0
                for leave in leaves_by_physician.get(ph_id, []):
                    total_reduction = min(
                        1.0,
                        total_reduction + _leave_reduction(
                            leave.start_date, leave.end_date,
                            leave.fte_during_leave,
                            year, month,
                        ),
                    )

                available_fraction = 1.0 - total_reduction
                ph_avail = base_monthly * available_fraction

                avail_hours += ph_avail
                avail_fte += fte_fraction * available_fraction
                clinical_hours += ph_avail * clinical_pct
                non_clinical_hours += ph_avail * (1.0 - clinical_pct)

            required_hours = demand_by_site_month.get((site.id, month), 0.0)
            required_fte = required_hours / avg_monthly_hours if avg_monthly_hours else 0.0

            rows.append(
                SiteMonthCapacity(
                    site_id=site.id,
                    site_name=site.name,
                    site_short_name=site.short_name,
                    year=year,
                    month=month,
                    available_hours=round(avail_hours, 1),
                    clinical_hours=round(clinical_hours, 1),
                    non_clinical_hours=round(non_clinical_hours, 1),
                    required_hours=round(required_hours, 1),
                    hours_gap=round(avail_hours - required_hours, 1),
                    available_fte=round(avail_fte, 2),
                    required_fte=round(required_fte, 2),
                    fte_gap=round(avail_fte - required_fte, 2),
                )
            )

    return CapacityResponse(year=year, site_id=site_id, rows=rows)
