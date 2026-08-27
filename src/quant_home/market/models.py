from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quant_home.db import Base


class CandleDataset(Base):
    __tablename__ = "candle_datasets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    interval: Mapped[str] = mapped_column(String(8), index=True, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    candle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reference_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    candles: Mapped[list["StoredCandle"]] = relationship(
        cascade="all, delete-orphan", back_populates="dataset"
    )
    issues: Mapped[list["DatasetValidationIssue"]] = relationship(
        cascade="all, delete-orphan", back_populates="dataset"
    )


class StoredCandle(Base):
    __tablename__ = "candles"

    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("candle_datasets.id", ondelete="CASCADE"), primary_key=True
    )
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    volume: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    dataset: Mapped[CandleDataset] = relationship(back_populates="candles")


class DatasetValidationIssue(Base):
    __tablename__ = "dataset_validation_issues"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("candle_datasets.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    open_time: Mapped[str | None] = mapped_column(String(40), nullable=True)

    dataset: Mapped[CandleDataset] = relationship(back_populates="issues")
