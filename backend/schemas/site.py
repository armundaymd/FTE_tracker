import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SiteAreaBase(BaseModel):
    name: str = Field(..., max_length=100)
    display_order: int = 0
    active: bool = True


class SiteAreaCreate(SiteAreaBase):
    pass


class SiteAreaRead(SiteAreaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    created_at: datetime


class SiteBase(BaseModel):
    name: str = Field(..., max_length=100)
    short_name: Optional[str] = Field(None, max_length=20)
    active: bool = True


class SiteCreate(SiteBase):
    areas: List[SiteAreaCreate] = []


class SiteUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    short_name: Optional[str] = Field(None, max_length=20)
    active: Optional[bool] = None


class SiteRead(SiteBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    areas: List[SiteAreaRead] = []
    created_at: datetime
    updated_at: datetime
