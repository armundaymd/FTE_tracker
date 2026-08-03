import uuid
from typing import List, Optional

from pydantic import BaseModel


class SiteMonthCapacity(BaseModel):
    site_id: uuid.UUID
    site_name: str
    site_short_name: Optional[str]
    year: int
    month: int
    available_hours: float
    clinical_hours: float
    non_clinical_hours: float
    required_hours: float
    hours_gap: float
    available_fte: float
    required_fte: float
    fte_gap: float


class CapacityResponse(BaseModel):
    year: int
    site_id: Optional[uuid.UUID]   # None = all sites
    rows: List[SiteMonthCapacity]
