from typing import List

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class TimeCategory(Base):
    """Lookup: the 10 category columns from the staffing spreadsheet (Adult ED, Admin, etc.)."""

    __tablename__ = "time_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    is_clinical: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    allocations: Mapped[List["TimeAllocation"]] = relationship(  # noqa: F821
        "TimeAllocation", back_populates="time_category"
    )
