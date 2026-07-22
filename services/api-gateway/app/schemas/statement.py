import uuid
from datetime import datetime

from app.db.models import FileFormat, FileTransferStatus
from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict


class StatementRead(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    filename: str
    format: FileFormat
    imported_at: datetime
    status: FileTransferStatus | None = None
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class StatementCreate(BaseModel):
    account_id: uuid.UUID
    file: UploadFile

    model_config = ConfigDict(from_attributes=True)


class StatementUpdate(BaseModel):
    account_id: uuid.UUID | None = None
    filename: str | None = None
    format: FileFormat | None = None

    model_config = ConfigDict(from_attributes=True)


class StatementDelete(BaseModel):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
