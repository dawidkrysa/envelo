import uuid

from pydantic import BaseModel, ConfigDict


class PayeeRead(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class PayeeCreate(BaseModel):
    name: str

    model_config = ConfigDict(from_attributes=True)


class PayeeUpdate(BaseModel):
    name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PayeeDelete(BaseModel):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
