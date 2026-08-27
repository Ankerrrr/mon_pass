from dataclasses import dataclass
from datetime import UTC
import hashlib
from typing import Sequence

from quant_home.market.candles import Candle, CandleInterval


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    open_time: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues


def validate_candles(
    candles: Sequence[Candle], interval: CandleInterval
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    for previous, current in zip(candles, candles[1:]):
        if current.open_time < previous.open_time:
            issues.append(
                ValidationIssue(
                    "OUT_OF_ORDER",
                    "Candles must be ordered by open time",
                    current.open_time.isoformat(),
                )
            )
    ordered = sorted(candles, key=lambda candle: candle.open_time)

    seen = set()
    previous_open_time = None
    for candle in ordered:
        timestamp = candle.open_time.isoformat()
        if candle.open_time.tzinfo is None or candle.open_time.utcoffset() is None:
            issues.append(ValidationIssue("NAIVE_TIMESTAMP", "Timestamp must be UTC", timestamp))
        elif candle.open_time.utcoffset() != UTC.utcoffset(candle.open_time):
            issues.append(ValidationIssue("NON_UTC_TIMESTAMP", "Timestamp must be UTC", timestamp))

        if candle.open_time in seen:
            issues.append(ValidationIssue("DUPLICATE_CANDLE", "Duplicate open time", timestamp))
        elif (
            previous_open_time is not None
            and candle.open_time - previous_open_time > interval.duration
        ):
            issues.append(ValidationIssue("MISSING_CANDLE", "Candle interval has a gap", timestamp))
        else:
            previous_open_time = candle.open_time
        seen.add(candle.open_time)

        prices_are_positive = min(candle.open, candle.high, candle.low, candle.close) > 0
        if not prices_are_positive:
            issues.append(ValidationIssue("NON_POSITIVE_PRICE", "Prices must be positive", timestamp))
        if candle.volume < 0:
            issues.append(ValidationIssue("NEGATIVE_VOLUME", "Volume cannot be negative", timestamp))
        if prices_are_positive and (
            candle.high < max(candle.open, candle.close)
            or candle.low > min(candle.open, candle.close)
            or candle.high < candle.low
        ):
            issues.append(ValidationIssue("INVALID_OHLC", "OHLC range is inconsistent", timestamp))
        expected_close = candle.open_time + interval.duration
        if not candle.open_time < candle.close_time <= expected_close:
            issues.append(ValidationIssue("INVALID_CLOSE_TIME", "Close time is outside interval", timestamp))

    unique = {
        (issue.code, issue.open_time): issue
        for issue in issues
    }
    return ValidationReport(tuple(unique.values()))


def dataset_fingerprint(candles: Sequence[Candle]) -> str:
    canonical = "\n".join(
        candle.model_dump_json()
        for candle in sorted(candles, key=lambda item: item.open_time)
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
