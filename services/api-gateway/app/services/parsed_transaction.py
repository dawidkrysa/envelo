from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ParsedTransaction(BaseModel):
    transaction_date: date
    amount: Decimal
    description: str | None
    payee: str | None
