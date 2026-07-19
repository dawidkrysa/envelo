import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class EnvelopeRead(BaseModel):
    id: uuid.UUID
    category_group_id: uuid.UUID
    name: str
    target_amount: Decimal | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EnvelopeCreate(BaseModel):
    category_group_id: uuid.UUID
    name: str
    target_amount: Decimal | None = Field(default=None, ge=0)

    model_config = ConfigDict(from_attributes=True)


class EnvelopeUpdate(BaseModel):
    category_group_id: uuid.UUID | None = None
    name: str | None = None
    target_amount: Decimal | None = Field(default=None, ge=0)

    model_config = ConfigDict(from_attributes=True)


class EnvelopeDelete(BaseModel):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
