from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from quant_home.configurations import models as configuration_models  # noqa: F401
from quant_home.db import Base
from quant_home.paper.types import ConnectionState, PaperSessionStatus


class PaperSession(Base):
    __tablename__ = "paper_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    configuration_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("strategy_configurations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    configuration_version: Mapped[int] = mapped_column(nullable=False)
    configuration_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    state_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[PaperSessionStatus] = mapped_column(
        Enum(PaperSessionStatus, native_enum=False), nullable=False, index=True
    )
    connection_state: Mapped[ConnectionState] = mapped_column(
        Enum(ConnectionState, native_enum=False), nullable=False
    )
    last_candle_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProcessedPaperCandle(Base):
    __tablename__ = "processed_paper_candles"

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("paper_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    strategy: Mapped[str] = mapped_column(String(32), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    interval: Mapped[str] = mapped_column(String(8), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
