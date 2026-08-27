from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from quant_home.backtest.config import (
    AllocationConfig,
    BacktestConfig,
    GridConfig,
    MeanReversionConfig,
    StrategyUniverse,
    SymbolWeight,
    TrendConfig,
)
from quant_home.market.candles import CandleInterval


def test_strategy_allocations_and_reserve_must_total_one():
    with pytest.raises(ValidationError, match="must total 1"):
        AllocationConfig(
            trend=Decimal("0.40"),
            mean_reversion=Decimal("0.30"),
            grid=Decimal("0.20"),
            cash_reserve=Decimal("0.20"),
        )


def test_symbol_weights_are_unique_and_total_one():
    with pytest.raises(ValidationError, match="unique"):
        StrategyUniverse(
            interval=CandleInterval.ONE_HOUR,
            symbols=(
                SymbolWeight(symbol="BTCUSDT", weight=Decimal("0.50")),
                SymbolWeight(symbol="BTCUSDT", weight=Decimal("0.50")),
            ),
        )

    with pytest.raises(ValidationError, match="must total 1"):
        StrategyUniverse(
            interval=CandleInterval.ONE_HOUR,
            symbols=(
                SymbolWeight(symbol="BTCUSDT", weight=Decimal("0.60")),
                SymbolWeight(symbol="ETHUSDT", weight=Decimal("0.30")),
            ),
        )


def test_strategy_parameter_relationships_are_validated():
    with pytest.raises(ValidationError, match="fast_period"):
        TrendConfig(fast_period=50, slow_period=20)

    with pytest.raises(ValidationError, match="rsi_entry"):
        MeanReversionConfig(rsi_entry=60, rsi_exit=55)

    with pytest.raises(ValidationError, match="lower_bound"):
        GridConfig(lower_bound=Decimal("110"), upper_bound=Decimal("100"))


def test_backtest_defaults_use_independent_strategy_intervals():
    config = BacktestConfig(
        start_time=datetime(2025, 1, 1, tzinfo=UTC),
        end_time=datetime(2025, 2, 1, tzinfo=UTC),
        universes={
            "trend": {"symbols": [{"symbol": "BTCUSDT", "weight": "1"}]},
            "mean_reversion": {
                "symbols": [{"symbol": "BTCUSDT", "weight": "1"}]
            },
            "grid": {"symbols": [{"symbol": "BTCUSDT", "weight": "1"}]},
        },
    )

    assert config.universes["trend"].interval is CandleInterval.FOUR_HOURS
    assert config.universes["mean_reversion"].interval is CandleInterval.ONE_HOUR
    assert config.universes["grid"].interval is CandleInterval.FIFTEEN_MINUTES
    assert config.allocations.cash_reserve == Decimal("0.10")


def test_backtest_range_requires_utc_and_positive_duration():
    payload = {
        "start_time": datetime(2025, 1, 2, tzinfo=UTC),
        "end_time": datetime(2025, 1, 1, tzinfo=UTC),
        "universes": {
            "trend": {"symbols": [{"symbol": "BTCUSDT", "weight": "1"}]},
            "mean_reversion": {
                "symbols": [{"symbol": "BTCUSDT", "weight": "1"}]
            },
            "grid": {"symbols": [{"symbol": "BTCUSDT", "weight": "1"}]},
        },
    }
    with pytest.raises(ValidationError, match="end_time"):
        BacktestConfig.model_validate(payload)

    payload["start_time"] = datetime(2025, 1, 1)
    payload["end_time"] = datetime(2025, 1, 2)
    with pytest.raises(ValidationError, match="UTC"):
        BacktestConfig.model_validate(payload)
