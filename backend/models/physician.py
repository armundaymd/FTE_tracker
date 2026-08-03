import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

if TYPE_CHECKING:
    from models.leave import Leave
    from models.site import Site


class ProviderType(Base):
    """Lookup: MD, DO, PA, NP, Fellow variants — matches provider_types table."""

    __tablename__ = "provider_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)   # "Physician" | "APP" | "Fellow"
    default_fte_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    physicians: Mapped[List["Physician"]] = relationship("Physician", back_populates="provider_type")


class RoleType(Base):
    """Lookup: administrative / academic role titles — matches role_types table."""

    __tablename__ = "role_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    category: Mapped[Optional[str]] = mapped_column(String(50))         # "Leadership" | "Research" | etc.
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    physician_roles: Mapped[List["PhysicianRole"]] = relationship(
        "PhysicianRole", back_populates="role_type"
    )


class Physician(Base):
    __tablename__ = "physicians"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Identity ────────────────────────────────────────────────────────────
    life_no: Mapped[Optional[str]] = mapped_column(String(20))          # institutional HR / Epic ID
    npi: Mapped[Optional[str]] = mapped_column(String(10))              # CHAR(10) in schema
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    provider_type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("provider_types.id"))

    # ── FTE / hours ─────────────────────────────────────────────────────────
    yearly_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    clinical_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("1.0"))
    total_fte: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))  # computed: sum of fte_fraction

    # ── Core / home site ────────────────────────────────────────────────────
    core_site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"))

    # ── Flags ────────────────────────────────────────────────────────────────
    is_core_faculty: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Free text ────────────────────────────────────────────────────────────
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # ── QGenda sync ──────────────────────────────────────────────────────────
    qgenda_staff_id: Mapped[Optional[str]] = mapped_column(String(100))
    qgenda_staff_key: Mapped[Optional[str]] = mapped_column(String(100))
    needs_fte_config: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # ── Term dates (fellows) ─────────────────────────────────────────────────
    term_start_date: Mapped[Optional[date]] = mapped_column(Date)
    term_end_date: Mapped[Optional[date]] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")

    __table_args__ = (
        CheckConstraint("clinical_pct >= 0 AND clinical_pct <= 1", name="chk_clinical_pct"),
        UniqueConstraint("npi",     name="uq_physicians_npi"),
        UniqueConstraint("life_no", name="uq_physicians_life_no"),
    )

    # ── Relationships ────────────────────────────────────────────────────────
    provider_type: Mapped[Optional["ProviderType"]] = relationship(
        "ProviderType", back_populates="physicians"
    )
    core_site: Mapped[Optional["Site"]] = relationship(
        "Site", foreign_keys=[core_site_id]
    )
    assignments: Mapped[List["SiteAssignment"]] = relationship(
        "SiteAssignment", back_populates="physician", cascade="all, delete-orphan"
    )
    roles: Mapped[List["PhysicianRole"]] = relationship(
        "PhysicianRole", back_populates="physician", cascade="all, delete-orphan"
    )
    leaves: Mapped[List["Leave"]] = relationship(
        "Leave", back_populates="physician", cascade="all, delete-orphan"
    )


class SiteAssignment(Base):
    """Physician ↔ Site with fractional FTE and time-bounded validity."""

    __tablename__ = "site_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    physician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("physicians.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False
    )
    fte_fraction: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, server_default="CURRENT_DATE")
    end_date: Mapped[Optional[date]] = mapped_column(Date)               # NULL = still active
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")

    __table_args__ = (
        CheckConstraint("fte_fraction > 0 AND fte_fraction <= 1", name="chk_fte_fraction"),
    )

    physician: Mapped["Physician"] = relationship("Physician", back_populates="assignments")
    site: Mapped["Site"] = relationship("Site", back_populates="assignments")


class PhysicianRole(Base):
    """Administrative / academic role held by a physician, with annual hour credit."""

    __tablename__ = "physician_roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    physician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("physicians.id", ondelete="CASCADE"), nullable=False
    )
    role_type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("role_types.id"))
    custom_title: Mapped[Optional[str]] = mapped_column(String(200))    # used when not in role_types
    hours_credit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pct_credit: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))  # alternative to hours_credit
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, server_default="CURRENT_DATE")
    end_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")

    physician: Mapped["Physician"] = relationship("Physician", back_populates="roles")
    role_type: Mapped[Optional["RoleType"]] = relationship("RoleType", back_populates="physician_roles")
