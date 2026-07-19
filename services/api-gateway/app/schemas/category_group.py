import uuid

from pydantic import BaseModel, ConfigDict


class CategoryGroupRead(BaseModel):
    id: uuid.UUID
    name: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class CategoryGroupCreate(BaseModel):
    name: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class CategoryGroupUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None

    model_config = ConfigDict(from_attributes=True)


class CategoryGroupDelete(BaseModel):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
