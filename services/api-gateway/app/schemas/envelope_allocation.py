import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class EnvelopeAllocationRead(BaseModel):
    id: uuid.UUID
    envelope_id: uuid.UUID
    month: date
    assigned_amount: Decimal

    model_config = ConfigDict(from_attributes=True)


class EnvelopeAllocationCreate(BaseModel):
    envelope_id: uuid.UUID
    month: date
    assigned_amount: Decimal = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class EnvelopeAllocationUpdate(BaseModel):
    envelope_id: uuid.UUID | None = None
    month: date | None = None
    assigned_amount: Decimal | None = Field(default=None, ge=0)

    model_config = ConfigDict(from_attributes=True)


class EnvelopeAllocationDelete(BaseModel):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)


class EnvelopeAllocationTransfer(BaseModel):
    from_envelope_id: uuid.UUID
    to_envelope_id: uuid.UUID
    month: date
    amount: Decimal = Field(gt=0)

    model_config = ConfigDict(from_attributes=True)
