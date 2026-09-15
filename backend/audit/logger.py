import uuid
from typing import Any, Optional, Type

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import CurrentUser
from models.audit_log import AuditLog

VALID_ACTIONS = {"INSERT", "UPDATE", "DELETE", "LOGIN", "SYNC", "EXPORT"}


def snapshot(schema_cls: Type[BaseModel], obj: Any) -> dict:
    """Serialize an ORM instance to a JSON-safe dict via its Pydantic Read schema."""
    return schema_cls.model_validate(obj).model_dump(mode="json")


async def log_audit(
    db: AsyncSession,
    user: CurrentUser,
    action: str,
    table_name: str,
    record_id: Optional[uuid.UUID],
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
) -> None:
    """
    Write one row to audit_log. Does not commit — the caller's own
    db.commit() (already happening in the mutating endpoint) persists it,
    so a single failed request rolls back the audit row along with the
    change it describes rather than logging a change that didn't happen.
    """
    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid audit action: {action!r}")

    db.add(
        AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=action,
            table_name=table_name,
            record_id=record_id,
            old_values=old_values,
            new_values=new_values,
        )
    )
