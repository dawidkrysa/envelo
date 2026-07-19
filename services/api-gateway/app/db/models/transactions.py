import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import TIMESTAMP, Date, ForeignKey, Numeric, text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base
from app.db.models.enums import CategorizationSource, FileFormat, get_enum_values
from app.db.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.budget import Account, Envelope, Payee
    from app.db.models.user import User


class Statement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "statements"
    __table_args__ = {"schema": "transactions"}

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("budget.accounts.id"), index=True
    )
    filename: Mapped[str]
    format: Mapped[FileFormat] = mapped_column(
        SqlEnum(FileFormat, values_callable=get_enum_values, native_enum=False)
    )
    imported_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()")
    )

    user: Mapped["User"] = relationship(back_populates="statements")
    account: Mapped["Account"] = relationship(back_populates="statements")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="statement")


class Transaction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = {"schema": "transactions"}

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("budget.accounts.id"), index=True
    )
    envelope_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("budget.envelopes.id"), index=True, nullable=True
    )
    payee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("budget.payees.id"), index=True, nullable=True
    )
    statement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transactions.statements.id"), index=True, nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric)
    currency: Mapped[str]
    description: Mapped[str | None] = mapped_column(nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date)
    cleared: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    categorization_source: Mapped[CategorizationSource | None] = mapped_column(
        SqlEnum(CategorizationSource, values_callable=get_enum_values, native_enum=False),
        nullable=True,
    )

    user: Mapped["User"] = relationship(back_populates="transactions")
    account: Mapped["Account"] = relationship(back_populates="transactions")
    envelope: Mapped["Envelope"] = relationship(back_populates="transactions")
    payee: Mapped["Payee"] = relationship(back_populates="transactions")
    statement: Mapped["Statement"] = relationship(back_populates="transactions")
