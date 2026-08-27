from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from quant_home.market.candles import Candle, CandleInterval
from quant_home.market.models import (
    CandleDataset,
    DatasetValidationIssue,
    StoredCandle,
)
from quant_home.market.validation import (
    ValidationReport,
    dataset_fingerprint,
    validate_candles,
)


class CandleDownloader(Protocol):
    def fetch_candles(
        self,
        symbol: str,
        interval: CandleInterval,
        start: datetime,
        end: datetime,
    ) -> Sequence[Candle]: ...


class DatasetInUse(Exception):
    pass


class DatasetNotFound(Exception):
    pass


class CandleRepository:
    def __init__(self, db: Session, downloader: CandleDownloader) -> None:
        self.db = db
        self.downloader = downloader

    def ensure_range(
        self,
        symbol: str,
        interval: CandleInterval,
        start: datetime,
        end: datetime,
        *,
        force_refresh: bool = False,
    ) -> CandleDataset:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start and end must include a UTC offset")
        start = start.astimezone(UTC)
        end = end.astimezone(UTC)
        if start >= end:
            raise ValueError("start must precede end")
        interval_microseconds = int(interval.duration.total_seconds() * 1_000_000)
        if (
            int(start.timestamp() * 1_000_000) % interval_microseconds
            or int(end.timestamp() * 1_000_000) % interval_microseconds
        ):
            raise ValueError("range must align to candle interval boundaries")
        symbol = symbol.upper()

        if not force_refresh:
            covering = self.db.scalar(
                select(CandleDataset)
                .where(
                    CandleDataset.symbol == symbol,
                    CandleDataset.interval == interval.value,
                    CandleDataset.is_valid.is_(True),
                    CandleDataset.start_time <= start,
                    CandleDataset.end_time >= end,
                )
                .order_by(CandleDataset.candle_count)
                .limit(1)
            )
            if covering is not None:
                return covering

        cached = {} if force_refresh else self._cached_candles(symbol, interval, start, end)
        expected_times = []
        current = start
        while current < end:
            expected_times.append(current)
            current += interval.duration

        missing_times = [timestamp for timestamp in expected_times if timestamp not in cached]
        raw_issues = []
        for missing_start, missing_end in self._contiguous_ranges(missing_times, interval):
            downloaded = list(
                self.downloader.fetch_candles(
                    symbol, interval, missing_start, missing_end
                )
            )
            raw_issues.extend(validate_candles(downloaded, interval).issues)
            for candle in downloaded:
                if start <= candle.open_time < end:
                    cached[candle.open_time] = candle

        candles = [cached[timestamp] for timestamp in expected_times if timestamp in cached]
        combined_issues = [*raw_issues, *validate_candles(candles, interval).issues]
        report = ValidationReport(
            tuple(
                {
                    (issue.code, issue.open_time): issue
                    for issue in combined_issues
                }.values()
            )
        )
        fingerprint = dataset_fingerprint(candles)
        existing = self.db.scalar(
            select(CandleDataset).where(
                CandleDataset.symbol == symbol,
                CandleDataset.interval == interval.value,
                CandleDataset.start_time == start,
                CandleDataset.end_time == end,
                CandleDataset.fingerprint == fingerprint,
            )
        )
        if existing is not None:
            return existing

        dataset = CandleDataset(
            symbol=symbol,
            interval=interval.value,
            start_time=start,
            end_time=end,
            fingerprint=fingerprint,
            candle_count=len(candles),
            is_valid=report.is_valid and len(candles) == len(expected_times),
        )
        dataset.candles = [
            StoredCandle(
                open_time=candle.open_time,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                close_time=candle.close_time,
            )
            for candle in candles
        ]
        dataset.issues = [
            DatasetValidationIssue(
                code=issue.code,
                message=issue.message,
                open_time=issue.open_time,
            )
            for issue in report.issues
        ]
        if len(candles) != len(expected_times) and not any(
            issue.code == "MISSING_CANDLE" for issue in dataset.issues
        ):
            dataset.issues.append(
                DatasetValidationIssue(
                    code="MISSING_CANDLE",
                    message="Requested range is incomplete",
                )
            )
        self.db.add(dataset)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            concurrent = self.db.scalar(
                select(CandleDataset).where(
                    CandleDataset.symbol == symbol,
                    CandleDataset.interval == interval.value,
                    CandleDataset.start_time == start,
                    CandleDataset.end_time == end,
                    CandleDataset.fingerprint == fingerprint,
                )
            )
            if concurrent is None:
                raise
            return concurrent
        return dataset

    def list(self) -> list[CandleDataset]:
        return list(
            self.db.scalars(
                select(CandleDataset).order_by(CandleDataset.created_at.desc())
            )
        )

    def get(self, dataset_id: UUID) -> CandleDataset:
        dataset = self.db.scalar(
            select(CandleDataset)
            .options(
                selectinload(CandleDataset.candles),
                selectinload(CandleDataset.issues),
            )
            .where(CandleDataset.id == dataset_id)
        )
        if dataset is None:
            raise DatasetNotFound
        return dataset

    def delete_unused(self, dataset_id: UUID) -> None:
        dataset = self.get(dataset_id)
        if dataset.reference_count:
            raise DatasetInUse
        self.db.delete(dataset)
        self.db.commit()

    def _cached_candles(
        self,
        symbol: str,
        interval: CandleInterval,
        start: datetime,
        end: datetime,
    ) -> dict[datetime, Candle]:
        records = self.db.scalars(
            select(StoredCandle)
            .join(CandleDataset)
            .where(
                CandleDataset.symbol == symbol,
                CandleDataset.interval == interval.value,
                CandleDataset.is_valid.is_(True),
                StoredCandle.open_time >= start,
                StoredCandle.open_time < end,
            )
        )
        return {
            self._as_utc(record.open_time): Candle(
                open_time=self._as_utc(record.open_time),
                open=record.open,
                high=record.high,
                low=record.low,
                close=record.close,
                volume=record.volume,
                close_time=self._as_utc(record.close_time),
            )
            for record in records
        }

    @staticmethod
    def _contiguous_ranges(
        missing_times: list[datetime], interval: CandleInterval
    ) -> list[tuple[datetime, datetime]]:
        if not missing_times:
            return []
        ranges = []
        range_start = previous = missing_times[0]
        for timestamp in missing_times[1:]:
            if timestamp - previous != interval.duration:
                ranges.append((range_start, previous + interval.duration))
                range_start = timestamp
            previous = timestamp
        ranges.append((range_start, previous + interval.duration))
        return ranges

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
