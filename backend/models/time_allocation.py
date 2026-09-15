import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

if TYPE_CHECKING:
    from models.physician import Physician
    from models.site import Site
    from models.time_category import TimeCategory


class TimeAllocation(Base):
    """Physician x site x category x month hours — the grid backing derived clinical_pct."""

    __tablename__ = "time_allocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    physician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("physicians.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"))
    time_category_id: Mapped[int] = mapped_column(Integer, ForeignKey("time_categories.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("0"))
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="chk_time_allocation_month"),
        CheckConstraint("hours >= 0", name="chk_time_allocation_hours"),
        UniqueConstraint("physician_id", "site_id", "time_category_id", "year", "month", name="uq_time_allocation"),
    )

    physician: Mapped["Physician"] = relationship("Physician", back_populates="time_allocations")
    site: Mapped[Optional["Site"]] = relationship("Site")
    time_category: Mapped["TimeCategory"] = relationship("TimeCategory", back_populates="allocations")
