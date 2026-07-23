import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from app.db.models.base import Base
from app.db.models.enums import AccountType, get_enum_values
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.db.models.transactions import Statement, Transaction
    from app.db.models.user import User


class Account(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = {"schema": "budget"}

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id"), index=True)
    name: Mapped[str]
    type: Mapped[AccountType] = mapped_column(
        SqlEnum(AccountType, values_callable=get_enum_values, native_enum=False)
    )
    currency: Mapped[str]

    user: Mapped["User"] = relationship(back_populates="accounts")
    statements: Mapped[list["Statement"]] = relationship(back_populates="account")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class CategoryGroup(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "category_groups"
    __table_args__ = {"schema": "budget"}

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id"), index=True)
    name: Mapped[str]
    sort_order: Mapped[int]

    user: Mapped["User"] = relationship(back_populates="category_groups")
    envelopes: Mapped[list["Envelope"]] = relationship(back_populates="category_group")


class Envelope(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "envelopes"
    __table_args__ = {"schema": "budget"}

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id"), index=True)
    category_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("budget.category_groups.id"), index=True
    )
    name: Mapped[str]
    target_amount: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    user: Mapped["User"] = relationship(back_populates="envelopes")
    category_group: Mapped["CategoryGroup"] = relationship(back_populates="envelopes")
    envelope_allocations: Mapped[list["EnvelopeAllocation"]] = relationship(
        back_populates="envelope"
    )
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="envelope")
    categorization_rules: Mapped[list["CategorizationRule"]] = relationship(
        back_populates="envelope"
    )


class EnvelopeAllocation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "envelope_allocations"
    __table_args__ = (
        UniqueConstraint("envelope_id", "month"),
        {"schema": "budget"},
    )

    envelope_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("budget.envelopes.id"), index=True
    )
    month: Mapped[date] = mapped_column(Date)
    assigned_amount: Mapped[Decimal] = mapped_column(Numeric)

    envelope: Mapped["Envelope"] = relationship(back_populates="envelope_allocations")


class Payee(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "payees"
    __table_args__ = {"schema": "budget"}

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id"), index=True)
    name: Mapped[str]

    user: Mapped["User"] = relationship(back_populates="payees")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="payee")


class CategorizationRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categorization_rules"
    __table_args__ = {"schema": "budget"}

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id"), index=True)
    envelope_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("budget.envelopes.id"), index=True
    )
    phrase: Mapped[str] = mapped_column(index=True)

    user: Mapped["User"] = relationship(back_populates="categorization_rules")
    envelope: Mapped["Envelope"] = relationship(back_populates="categorization_rules")
