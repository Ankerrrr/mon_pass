from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant_home.backtest.metrics import calculate_metrics
from quant_home.backtest.types import EquityPoint, Fill


def _point(day: int, equity: str) -> EquityPoint:
    return EquityPoint(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(days=day),
        equity=Decimal(equity),
        cash=Decimal(equity),
        exposure=Decimal("0"),
    )


def test_calculate_metrics_reports_returns_drawdown_and_sharpe():
    metrics = calculate_metrics(
        (_point(0, "100"), _point(1, "120"), _point(2, "90"), _point(3, "110")),
        (),
        annualization_periods=3,
    )

    assert metrics.total_return == Decimal("0.1")
    assert metrics.annualized_return == Decimal("0.1")
    assert metrics.max_drawdown == Decimal("0.25")
    assert metrics.sharpe == pytest.approx(0.373169, rel=1e-5)


def test_calculate_metrics_derives_closed_trade_statistics_and_fees():
    fills = (
        Fill.buy("BTCUSDT", Decimal("2"), Decimal("100"), Decimal("2")),
        Fill.sell("BTCUSDT", Decimal("1"), Decimal("130"), Decimal("1")),
        Fill.sell("BTCUSDT", Decimal("1"), Decimal("90"), Decimal("1")),
    )

    metrics = calculate_metrics((_point(0, "100"), _point(1, "100")), fills)

    assert metrics.trade_count == 2
    assert metrics.win_rate == Decimal("0.5")
    assert metrics.profit_factor == Decimal("28") / Decimal("12")
    assert metrics.fees == Decimal("4")


def test_calculate_metrics_returns_zeroes_for_an_empty_curve():
    metrics = calculate_metrics((), ())

    assert metrics.total_return == 0
    assert metrics.annualized_return == 0
    assert metrics.max_drawdown == 0
    assert metrics.sharpe == 0
    assert metrics.trade_count == 0
    assert metrics.win_rate == 0
    assert metrics.profit_factor == 0
    assert metrics.fees == 0


def test_calculate_metrics_rejects_non_positive_annualization_periods():
    with pytest.raises(ValueError, match="annualization_periods must be positive"):
        calculate_metrics((_point(0, "100"), _point(1, "110")), (), annualization_periods=0)
