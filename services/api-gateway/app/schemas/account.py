import uuid
from datetime import datetime
from decimal import Decimal

from app.db.models import AccountType
from pydantic import BaseModel, ConfigDict


class AccountRead(BaseModel):
    id: uuid.UUID
    name: str
    type: AccountType
    currency: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountBalanceRead(BaseModel):
    """One account's standing, as returned by `GET /budget/accounts/balances`.

    `balance` is signed - the sum of every transaction on the account, so a
    credit card in debt reports a negative. `last_imported_at` is `None` for an
    account no statement has ever been uploaded to.
    """

    account_id: uuid.UUID
    balance: Decimal
    transaction_count: int
    last_imported_at: datetime | None = None

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
