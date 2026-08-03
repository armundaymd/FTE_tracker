import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

if TYPE_CHECKING:
    from models.physician import Physician


class Leave(Base):
    __tablename__ = "leaves"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    physician_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("physicians.id", ondelete="CASCADE"), nullable=False
    )
    # Mirrors the CHECK constraint in schema.sql — validated at the Pydantic layer too
    leave_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    is_partial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    fte_during_leave: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))  # effective FTE; NULL = fully out
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))  # FK to users.id — Phase 2
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="chk_leave_dates"),
        CheckConstraint(
            "leave_type IN ("
            "'FMLA','LOA','Research Protected Time',"
            "'Maternity/Paternity','Medical','Administrative','Other'"
            ")",
            name="chk_leave_type",
        ),
    )

    physician: Mapped["Physician"] = relationship("Physician", back_populates="leaves")
