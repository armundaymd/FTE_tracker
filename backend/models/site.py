import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

if TYPE_CHECKING:
    from models.demand import MonthlyDemand
    from models.physician import SiteAssignment


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    areas: Mapped[List["SiteArea"]] = relationship(
        "SiteArea", back_populates="site", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["SiteAssignment"]] = relationship(
        "SiteAssignment", back_populates="site"
    )
    demand: Mapped[List["MonthlyDemand"]] = relationship(
        "MonthlyDemand", back_populates="site", cascade="all, delete-orphan"
    )


class SiteArea(Base):
    __tablename__ = "site_areas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    site: Mapped["Site"] = relationship("Site", back_populates="areas")
