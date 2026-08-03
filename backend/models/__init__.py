# Import all ORM models here so SQLAlchemy registers them with Base.metadata
# before create_all / Alembic autogenerate runs.
# Order: lookup tables first, then entities that reference them.
from models.site import Site, SiteArea
from models.physician import PhysicianRole, ProviderType, RoleType, Physician, SiteAssignment
from models.leave import Leave
from models.demand import MonthlyDemand

# Phase 2: User, AuditLog, QgendaSyncLog will be added to models/user.py

__all__ = [
    "Site",
    "SiteArea",
    "ProviderType",
    "RoleType",
    "Physician",
    "SiteAssignment",
    "PhysicianRole",
    "Leave",
    "MonthlyDemand",
]
