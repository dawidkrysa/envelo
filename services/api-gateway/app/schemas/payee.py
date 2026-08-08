import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PayeeRead(BaseModel):
    id: uuid.UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class PayeeStatsRead(BaseModel):
    """One payee's history, as returned by `GET /budget/payees/stats`.

    `total` is signed - the sum of every transaction, so a payee you only pay
    reports a negative and one that pays you (an employer, a refund) reports a
    positive. `top_envelope_id` is where this payee's transactions most often
    end up, and is `None` for a payee whose transactions are all uncategorized.
    """

    payee_id: uuid.UUID
    total: Decimal
    transaction_count: int
    last_transaction_date: date | None = None
    top_envelope_id: uuid.UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PayeeMerge(BaseModel):
    """Fold `from_payee_id` into `into_payee_id`: the first one's transactions
    are repointed at the second, then it is deleted."""

    from_payee_id: uuid.UUID
    into_payee_id: uuid.UUID

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
