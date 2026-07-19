import uuid
from datetime import date
from decimal import Decimal

from app.db.models import CategorizationSource
from pydantic import BaseModel, ConfigDict, field_validator


def _amount_must_not_be_zero(v: Decimal | None) -> Decimal | None:
    if v is not None and v == 0:
        raise ValueError("Transaction amount cannot be zero")
    return v


class TransactionRead(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    envelope_id: uuid.UUID | None
    payee_id: uuid.UUID | None
    statement_id: uuid.UUID | None
    amount: Decimal
    currency: str
    description: str | None
    transaction_date: date
    cleared: bool
    categorization_source: CategorizationSource | None

    model_config = ConfigDict(from_attributes=True)


class TransactionCreate(BaseModel):
    account_id: uuid.UUID
    envelope_id: uuid.UUID | None = None
    payee_id: uuid.UUID | None = None
    statement_id: uuid.UUID | None = None
    amount: Decimal
    currency: str
    description: str | None = None
    transaction_date: date
    cleared: bool = False
    categorization_source: CategorizationSource | None = None

    model_config = ConfigDict(from_attributes=True)

    _validate_amount = field_validator("amount")(_amount_must_not_be_zero)


class TransactionUpdate(BaseModel):
    account_id: uuid.UUID | None = None
    envelope_id: uuid.UUID | None = None
    payee_id: uuid.UUID | None = None
    statement_id: uuid.UUID | None = None
    amount: Decimal | None = None
    currency: str | None = None
    description: str | None = None
    transaction_date: date | None = None
    cleared: bool | None = None
    categorization_source: CategorizationSource | None = None

    model_config = ConfigDict(from_attributes=True)

    _validate_amount = field_validator("amount")(_amount_must_not_be_zero)


class TransactionDelete(BaseModel):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
