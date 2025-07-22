from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, examples=["payment-service"])
    display_name: str = Field(min_length=1, max_length=256, examples=["Payment Service"])
    environment: str = Field(default="production", max_length=64)
    description: str | None = None
    owner_team: str | None = Field(default=None, max_length=128)


class ServiceUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=256)
    environment: str | None = Field(default=None, max_length=64)
    description: str | None = None
    owner_team: str | None = Field(default=None, max_length=128)


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    display_name: str
    environment: str
    description: str | None
    owner_team: str | None
    created_at: datetime
    updated_at: datetime
