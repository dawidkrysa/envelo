import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from app.db.models.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.db.models.user import User


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = {"schema": "auth"}

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("auth.users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("auth.refresh_tokens.id"))
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)

    user: Mapped["User"] = relationship(back_populates="tokens")
