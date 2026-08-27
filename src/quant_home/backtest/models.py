from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from quant_home.db import Base


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    configuration_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    dataset_fingerprints: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False
    )
    result_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(40), nullable=False)
    fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
