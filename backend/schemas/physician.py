import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Lookup tables (read-only from the API's perspective) ───────────────────

class ProviderTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    default_fte_hours: int
    display_order: int


class RoleTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: Optional[str]
    display_order: int


# ── Site assignments ────────────────────────────────────────────────────────

class SiteAssignmentBase(BaseModel):
    site_id: uuid.UUID
    fte_fraction: Decimal = Field(..., gt=0, le=1)
    effective_date: date = Field(default_factory=date.today)
    end_date: Optional[date] = None
    notes: Optional[str] = None


class SiteAssignmentCreate(SiteAssignmentBase):
    pass


class SiteAssignmentUpdate(BaseModel):
    fte_fraction: Optional[Decimal] = Field(None, gt=0, le=1)
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None


class SiteAssignmentRead(SiteAssignmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    physician_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ── Physician roles ─────────────────────────────────────────────────────────

class PhysicianRoleBase(BaseModel):
    role_type_id: Optional[int] = None
    custom_title: Optional[str] = Field(None, max_length=200)
    hours_credit: int = 0
    pct_credit: Optional[Decimal] = None
    effective_date: date = Field(default_factory=date.today)
    end_date: Optional[date] = None
    notes: Optional[str] = None


class PhysicianRoleCreate(PhysicianRoleBase):
    pass


class PhysicianRoleUpdate(BaseModel):
    role_type_id: Optional[int] = None
    custom_title: Optional[str] = Field(None, max_length=200)
    hours_credit: Optional[int] = None
    pct_credit: Optional[Decimal] = None
    effective_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None


class PhysicianRoleRead(PhysicianRoleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    physician_id: uuid.UUID
    role_type: Optional[RoleTypeRead] = None
    created_at: datetime


# ── Physician ───────────────────────────────────────────────────────────────

class PhysicianBase(BaseModel):
    life_no: Optional[str] = Field(None, max_length=20)
    npi: Optional[str] = Field(None, max_length=10)
    last_name: str = Field(..., max_length=100)
    first_name: str = Field(..., max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    provider_type_id: Optional[int] = None
    yearly_hours: int = 1440
    clinical_pct: Decimal = Field(Decimal("1.0"), ge=0, le=1)
    core_site_id: Optional[uuid.UUID] = None
    is_core_faculty: bool = False
    is_active: bool = True
    notes: Optional[str] = None
    term_start_date: Optional[date] = None
    term_end_date: Optional[date] = None


class PhysicianCreate(PhysicianBase):
    assignments: List[SiteAssignmentCreate] = []
    roles: List[PhysicianRoleCreate] = []


class PhysicianUpdate(BaseModel):
    life_no: Optional[str] = Field(None, max_length=20)
    npi: Optional[str] = Field(None, max_length=10)
    last_name: Optional[str] = Field(None, max_length=100)
    first_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    provider_type_id: Optional[int] = None
    yearly_hours: Optional[int] = None
    clinical_pct: Optional[Decimal] = Field(None, ge=0, le=1)
    core_site_id: Optional[uuid.UUID] = None
    is_core_faculty: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    term_start_date: Optional[date] = None
    term_end_date: Optional[date] = None


class PhysicianRead(PhysicianBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    total_fte: Optional[Decimal] = None
    provider_type: Optional[ProviderTypeRead] = None
    qgenda_staff_id: Optional[str] = None
    qgenda_staff_key: Optional[str] = None
    needs_fte_config: bool = False
    last_synced_at: Optional[datetime] = None
    assignments: List[SiteAssignmentRead] = []
    roles: List[PhysicianRoleRead] = []
    created_at: datetime
    updated_at: datetime


class PhysicianListItem(BaseModel):
    """Lightweight read model for roster list — omits nested assignments/roles."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    life_no: Optional[str]
    last_name: str
    first_name: str
    provider_type_id: Optional[int]
    yearly_hours: int
    clinical_pct: Decimal
    total_fte: Optional[Decimal]
    core_site_id: Optional[uuid.UUID]
    is_active: bool
    needs_fte_config: bool
