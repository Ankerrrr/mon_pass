from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quant_home.db import Base


class Administrator(Base):
    __tablename__ = "administrators"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    sessions: Mapped[list["AdminSession"]] = relationship(
        back_populates="administrator",
        cascade="all, delete-orphan",
    )


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    administrator_id: Mapped[UUID] = mapped_column(
        ForeignKey("administrators.id", ondelete="CASCADE"),
        nullable=False,
    )
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    administrator: Mapped[Administrator] = relationship(back_populates="sessions")
