import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class ErrorLog(Base):
    __tablename__ = "error_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    error_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)  # shown to the user, grep-able
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    exception_type: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    traceback: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))     # best-effort — decoded from the bearer token, if any
    user_email: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
