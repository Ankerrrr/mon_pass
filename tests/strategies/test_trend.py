from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant_home.backtest.config import TrendConfig
from quant_home.backtest.types import Position, Side
from quant_home.market.candles import Candle
from quant_home.strategies.base import CandleWindow, StrategyState
from quant_home.strategies.trend import TrendStrategy


def candles(closes: list[str]) -> tuple[Candle, ...]:
    result = []
    for index, close_text in enumerate(closes):
        opened = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=index)
        close = Decimal(close_text)
        result.append(
            Candle(
                open_time=opened,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=Decimal("1"),
                close_time=opened + timedelta(hours=1),
            )
        )
    return tuple(result)


def test_trend_enters_after_confirmed_cross_and_exits_on_trailing_stop():
    series = candles(["3", "2", "1", "2", "3", "4", "4", "2.8"])
    strategy = TrendStrategy(
        TrendConfig(
            moving_average="sma",
            fast_period=2,
            slow_period=3,
            fixed_stop_loss=Decimal("0.03"),
            trailing_stop=Decimal("0.05"),
        )
    )

    entry = strategy.generate(4, CandleWindow(series, 4), StrategyState())
    exit_signals = strategy.generate(
        7,
        CandleWindow(series, 7),
        StrategyState(
            positions={
                "BTCUSDT": Position(
                    symbol="BTCUSDT",
                    quantity=Decimal("1"),
                    average_price=Decimal("3"),
                )
            },
            values={"symbol": "BTCUSDT", "peak_price": Decimal("4")},
        ),
    )

    assert [(signal.side, signal.reason) for signal in entry] == [
        (Side.BUY, "FAST_ABOVE_SLOW")
    ]
    assert [(signal.side, signal.reason) for signal in exit_signals] == [
        (Side.SELL, "TRAILING_STOP")
    ]


def test_trend_signal_does_not_read_future_candles():
    prefix = ["3", "2", "1", "2", "3"]
    strategy = TrendStrategy(
        TrendConfig(moving_average="sma", fast_period=2, slow_period=3)
    )

    high_future = strategy.generate(
        4, CandleWindow(candles(prefix + ["999"]), 4), StrategyState()
    )
    low_future = strategy.generate(
        4, CandleWindow(candles(prefix + ["0.01"]), 4), StrategyState()
    )

    assert high_future == low_future
    assert high_future[0].reason == "FAST_ABOVE_SLOW"


def test_trend_respects_entry_cooldown():
    series = candles(["3", "2", "1", "2", "3"])
    strategy = TrendStrategy(
        TrendConfig(
            moving_average="sma",
            fast_period=2,
            slow_period=3,
            cooldown_candles=2,
        )
    )

    signals = strategy.generate(
        4,
        CandleWindow(series, 4),
        StrategyState(values={"symbol": "BTCUSDT", "last_exit_index": 3}),
    )

    assert signals == []
