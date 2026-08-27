from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant_home.backtest.config import GridConfig
from quant_home.backtest.types import Position, Side
from quant_home.market.candles import Candle
from quant_home.strategies.base import CandleWindow, StrategyState
from quant_home.strategies.grid import GridStrategy, build_grid, crossed_levels


def candle(open_: str, low: str, high: str, close: str) -> Candle:
    opened = datetime(2025, 1, 1, tzinfo=UTC)
    return Candle(
        open_time=opened,
        open=Decimal(open_),
        low=Decimal(low),
        high=Decimal(high),
        close=Decimal(close),
        volume=Decimal("1"),
        close_time=opened + timedelta(hours=1),
    )


def test_builds_arithmetic_and_geometric_grid_levels():
    arithmetic = build_grid(
        GridConfig(lower_bound=Decimal("90"), upper_bound=Decimal("110"), grid_count=4)
    )
    geometric = build_grid(
        GridConfig(
            lower_bound=Decimal("100"),
            upper_bound=Decimal("400"),
            grid_count=2,
            spacing="geometric",
        )
    )

    assert arithmetic == tuple(map(Decimal, ("90", "95", "100", "105", "110")))
    assert geometric == tuple(map(Decimal, ("100", "200", "400")))


def test_crossed_levels_follow_documented_conservative_price_path():
    levels = tuple(map(Decimal, ("90", "95", "100", "105")))

    crossings = crossed_levels(candle("100", "90", "105", "95"), levels)

    assert [item.level for item in crossings] == list(
        map(Decimal, ("95", "90", "95", "100", "105", "100", "95"))
    )
    assert [item.side for item in crossings[:3]] == [Side.BUY, Side.BUY, Side.SELL]


def test_grid_does_not_add_inventory_at_configured_limit():
    config = GridConfig(
        lower_bound=Decimal("90"),
        upper_bound=Decimal("110"),
        grid_count=4,
        maximum_inventory=Decimal("0.50"),
    )
    strategy = GridStrategy(config)
    state = StrategyState(
        positions={
            "BTCUSDT": Position(
                symbol="BTCUSDT", quantity=Decimal("5"), average_price=Decimal("100")
            )
        },
        values={"symbol": "BTCUSDT", "inventory_fraction": Decimal("0.50")},
    )

    signals = strategy.generate(
        0,
        CandleWindow((candle("100", "90", "100", "95"),), 0),
        state,
    )

    assert all(signal.side is not Side.BUY for signal in signals)


def test_default_out_of_range_behavior_preserves_inventory():
    strategy = GridStrategy(
        GridConfig(lower_bound=Decimal("90"), upper_bound=Decimal("110"), grid_count=4)
    )
    state = StrategyState(
        positions={
            "BTCUSDT": Position(
                symbol="BTCUSDT", quantity=Decimal("2"), average_price=Decimal("100")
            )
        },
        values={"symbol": "BTCUSDT"},
    )

    signals = strategy.generate(
        0,
        CandleWindow((candle("111", "111", "120", "120"),), 0),
        state,
    )

    assert signals == []
