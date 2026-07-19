import uuid
from datetime import datetime

from app.db.models import AccountType
from pydantic import BaseModel, ConfigDict


class AccountRead(BaseModel):
    id: uuid.UUID
    name: str
    type: AccountType
    currency: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountCreate(BaseModel):
    name: str
    type: AccountType
    currency: str

    model_config = ConfigDict(from_attributes=True)


class AccountDelete(BaseModel):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class AccountUpdate(BaseModel):
    name: str | None = None
    type: AccountType | None = None
    currency: str | None = None

    model_config = ConfigDict(from_attributes=True)
