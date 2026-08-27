from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from quant_home.db import Base
from quant_home.jobs import models as job_models  # noqa: F401


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("background_jobs.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )
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
