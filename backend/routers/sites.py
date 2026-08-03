import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db import get_db
from models.site import Site, SiteArea
from schemas.site import SiteAreaCreate, SiteCreate, SiteRead, SiteUpdate

router = APIRouter()


async def _get_site_or_404(site_id: uuid.UUID, db: AsyncSession) -> Site:
    result = await db.execute(
        select(Site)
        .where(Site.id == site_id)
        .options(selectinload(Site.areas))
    )
    site = result.scalar_one_or_none()
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.get("/", response_model=List[SiteRead])
async def list_sites(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Site)
        .where(Site.active == True)
        .options(selectinload(Site.areas))
        .order_by(Site.name)
    )
    return result.scalars().all()


@router.post("/", response_model=SiteRead, status_code=status.HTTP_201_CREATED)
async def create_site(payload: SiteCreate, db: AsyncSession = Depends(get_db)):
    site = Site(name=payload.name, short_name=payload.short_name, active=payload.active)
    db.add(site)
    await db.flush()  # materialise site.id before creating child areas

    for area_data in payload.areas:
        db.add(SiteArea(site_id=site.id, **area_data.model_dump()))

    await db.commit()

    # Re-fetch with relationships loaded
    return await _get_site_or_404(site.id, db)


@router.patch("/{site_id}", response_model=SiteRead)
async def update_site(
    site_id: uuid.UUID,
    payload: SiteUpdate,
    db: AsyncSession = Depends(get_db),
):
    site = await _get_site_or_404(site_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(site, field, value)
    await db.commit()
    return await _get_site_or_404(site_id, db)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_site(site_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    site = await _get_site_or_404(site_id, db)
    site.active = False
    await db.commit()


# ── Site areas sub-resource ────────────────────────────────────────────────

@router.post(
    "/{site_id}/areas",
    response_model=SiteRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_site_area(
    site_id: uuid.UUID,
    payload: SiteAreaCreate,
    db: AsyncSession = Depends(get_db),
):
    site = await _get_site_or_404(site_id, db)
    db.add(SiteArea(site_id=site.id, **payload.model_dump()))
    await db.commit()
    return await _get_site_or_404(site_id, db)


@router.delete("/{site_id}/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_site_area(
    site_id: uuid.UUID,
    area_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SiteArea)
        .where(SiteArea.id == area_id)
        .where(SiteArea.site_id == site_id)
    )
    area = result.scalar_one_or_none()
    if area is None:
        raise HTTPException(status_code=404, detail="Area not found")
    await db.delete(area)
    await db.commit()
