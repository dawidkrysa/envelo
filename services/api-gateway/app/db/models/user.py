from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.budget import Account, CategoryGroup, Envelope, Payee
    from app.db.models.transactions import Statement, Transaction


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]

    accounts: Mapped[list["Account"]] = relationship(back_populates="user")
    category_groups: Mapped[list["CategoryGroup"]] = relationship(back_populates="user")
    envelopes: Mapped[list["Envelope"]] = relationship(back_populates="user")
    payees: Mapped[list["Payee"]] = relationship(back_populates="user")
    statements: Mapped[list["Statement"]] = relationship(back_populates="user")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
