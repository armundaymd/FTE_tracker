# Import all ORM models here so SQLAlchemy registers them with Base.metadata
# before create_all / Alembic autogenerate runs.
# Order: lookup tables first, then entities that reference them.
from models.site import Site, SiteArea
from models.time_category import TimeCategory
from models.physician import PhysicianRole, ProviderType, RoleType, Physician, SiteAssignment
from models.time_allocation import TimeAllocation
from models.leave import Leave
from models.demand import MonthlyDemand
from models.user import User
from models.audit_log import AuditLog
from models.error_log import ErrorLog

# Phase 2: QgendaSyncLog will be added later

__all__ = [
    "Site",
    "SiteArea",
    "TimeCategory",
    "ProviderType",
    "RoleType",
    "Physician",
    "SiteAssignment",
    "PhysicianRole",
    "TimeAllocation",
    "Leave",
    "MonthlyDemand",
    "User",
    "AuditLog",
    "ErrorLog",
]
