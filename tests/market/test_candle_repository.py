from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from quant_home.db import Base
from quant_home.market.candles import Candle, CandleInterval
from quant_home.market.repository import CandleRepository, DatasetInUse


class RecordingDownloader:
    def __init__(self) -> None:
        self.calls: list[tuple[datetime, datetime]] = []

    def fetch_candles(self, symbol, interval, start, end):
        self.calls.append((start, end))
        candles = []
        current = start
        while current < end:
            candles.append(
                Candle(
                    open_time=current,
                    open=Decimal("100"),
                    high=Decimal("102"),
                    low=Decimal("99"),
                    close=Decimal("101"),
                    volume=Decimal("10"),
                    close_time=current
                    + interval.duration
                    - timedelta(milliseconds=1),
                )
            )
            current += interval.duration
        return candles


class EmptyDownloader:
    def fetch_candles(self, symbol, interval, start, end):
        return []


class DuplicateDownloader(RecordingDownloader):
    def fetch_candles(self, symbol, interval, start, end):
        candles = super().fetch_candles(symbol, interval, start, end)
        return [candles[0], candles[0]]


def test_overlapping_range_downloads_only_missing_candles():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    downloader = RecordingDownloader()
    start = datetime(2026, 1, 1, tzinfo=UTC)

    with Session(engine) as db:
        repository = CandleRepository(db, downloader)
        first = repository.ensure_range(
            "BTCUSDT", CandleInterval.ONE_HOUR, start, start + timedelta(hours=3)
        )
        second = repository.ensure_range(
            "BTCUSDT",
            CandleInterval.ONE_HOUR,
            start + timedelta(hours=1),
            start + timedelta(hours=4),
        )

        assert first.candle_count == 3
        assert second.candle_count == 3
        assert len(first.fingerprint) == 64
        assert downloader.calls == [
            (start, start + timedelta(hours=3)),
            (start + timedelta(hours=3), start + timedelta(hours=4)),
        ]


def test_referenced_dataset_cannot_be_deleted():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    start = datetime(2026, 1, 1, tzinfo=UTC)

    with Session(engine) as db:
        repository = CandleRepository(db, RecordingDownloader())
        dataset = repository.ensure_range(
            "BTCUSDT", CandleInterval.ONE_HOUR, start, start + timedelta(hours=1)
        )
        dataset.reference_count = 1
        db.commit()

        with pytest.raises(DatasetInUse):
            repository.delete_unused(dataset.id)


def test_identical_content_does_not_cross_dataset_metadata_boundaries():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    start = datetime(2026, 1, 1, tzinfo=UTC)

    with Session(engine) as db:
        repository = CandleRepository(db, EmptyDownloader())
        btc = repository.ensure_range(
            "BTCUSDT", CandleInterval.ONE_HOUR, start, start + timedelta(hours=1)
        )
        eth = repository.ensure_range(
            "ETHUSDT", CandleInterval.ONE_HOUR, start, start + timedelta(hours=1)
        )

        assert btc.id != eth.id
        assert eth.symbol == "ETHUSDT"


def test_raw_duplicate_is_persisted_as_validation_issue():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    start = datetime(2026, 1, 1, tzinfo=UTC)

    with Session(engine) as db:
        repository = CandleRepository(db, DuplicateDownloader())
        dataset = repository.ensure_range(
            "BTCUSDT", CandleInterval.ONE_HOUR, start, start + timedelta(hours=1)
        )
        loaded = repository.get(dataset.id)

        assert loaded.is_valid is False
        assert {issue.code for issue in loaded.issues} == {"DUPLICATE_CANDLE"}
