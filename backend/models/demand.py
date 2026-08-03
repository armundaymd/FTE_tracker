import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, SmallInteger, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

if TYPE_CHECKING:
    from models.site import Site


class MonthlyDemand(Base):
    __tablename__ = "monthly_demand"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    month: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hours_required: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))  # FK to users.id — Phase 2
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default="now()")

    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="chk_month"),
        UniqueConstraint("site_id", "year", "month", name="uq_monthly_demand"),
    )

    site: Mapped["Site"] = relationship("Site", back_populates="demand")
