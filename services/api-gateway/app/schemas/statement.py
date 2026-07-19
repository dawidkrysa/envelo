import uuid
from datetime import datetime

from app.db.models import FileFormat
from pydantic import BaseModel, ConfigDict


class StatementRead(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    filename: str
    format: FileFormat
    imported_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StatementCreate(BaseModel):
    account_id: uuid.UUID
    filename: str
    format: FileFormat

    model_config = ConfigDict(from_attributes=True)


class StatementUpdate(BaseModel):
    account_id: uuid.UUID | None = None
    filename: str | None = None
    format: FileFormat | None = None

    model_config = ConfigDict(from_attributes=True)


class StatementDelete(BaseModel):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
