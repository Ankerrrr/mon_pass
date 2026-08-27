from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant_home.market.candles import Candle, CandleInterval
from quant_home.market.validation import validate_candles


def candle(hour: int, close: str = "101", high: str = "102") -> Candle:
    opened = datetime(2026, 1, 1, hour, tzinfo=UTC)
    return Candle(
        open_time=opened,
        open=Decimal("100"),
        high=Decimal(high),
        low=Decimal("99"),
        close=Decimal(close),
        volume=Decimal("10"),
        close_time=opened + timedelta(hours=1) - timedelta(milliseconds=1),
    )


def test_validation_rejects_gap_and_non_positive_price():
    report = validate_candles(
        [candle(0), candle(2, close="0")],
        CandleInterval.ONE_HOUR,
    )

    assert report.is_valid is False
    assert {issue.code for issue in report.issues} == {
        "MISSING_CANDLE",
        "NON_POSITIVE_PRICE",
    }


def test_validation_rejects_duplicate_and_invalid_ohlc_range():
    malformed = candle(1, high="100")

    report = validate_candles(
        [candle(0), malformed, malformed],
        CandleInterval.ONE_HOUR,
    )

    assert report.is_valid is False
    assert {issue.code for issue in report.issues} == {
        "DUPLICATE_CANDLE",
        "INVALID_OHLC",
    }
