from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant_home.backtest.config import MeanReversionConfig
from quant_home.backtest.types import Position, Side
from quant_home.market.candles import Candle
from quant_home.strategies.base import CandleWindow, StrategyState
from quant_home.strategies.mean_reversion import MeanReversionStrategy


def candles(closes: list[str]) -> tuple[Candle, ...]:
    result = []
    for index, text in enumerate(closes):
        opened = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=index)
        close = Decimal(text)
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


def strategy() -> MeanReversionStrategy:
    return MeanReversionStrategy(
        MeanReversionConfig(
            rsi_period=2,
            rsi_entry=Decimal("30"),
            rsi_exit=Decimal("55"),
            bollinger_period=3,
            bollinger_stddev=Decimal("1"),
            staged_entries=2,
            staged_entry_distance=Decimal("0.05"),
            max_holding_candles=5,
            stop_loss=Decimal("0.50"),
            take_profit=Decimal("0.50"),
        )
    )


def test_mean_reversion_requires_rsi_and_lower_band():
    series = candles(["100", "100", "100", "90", "50"])

    signals = strategy().generate(4, CandleWindow(series, 4), StrategyState())

    assert len(signals) == 1
    assert signals[0].side is Side.BUY
    assert signals[0].reason == "RSI_AND_LOWER_BAND"
    assert signals[0].allocation == Decimal("0.5")


def test_staged_entry_requires_configured_price_distance():
    position = Position(
        symbol="BTCUSDT", quantity=Decimal("1"), average_price=Decimal("60")
    )
    base_state = {
        "positions": {"BTCUSDT": position},
        "values": {"symbol": "BTCUSDT", "entry_count": 1, "last_entry_price": Decimal("52")},
    }

    too_close = strategy().generate(
        4,
        CandleWindow(candles(["100", "100", "100", "90", "50"]), 4),
        StrategyState(**base_state),
    )
    far_enough = strategy().generate(
        4,
        CandleWindow(candles(["100", "100", "100", "90", "49"]), 4),
        StrategyState(**base_state),
    )

    assert too_close == []
    assert far_enough[0].reason == "STAGED_ENTRY"


def test_maximum_holding_period_exits_position():
    position = Position(
        symbol="BTCUSDT", quantity=Decimal("2"), average_price=Decimal("100")
    )

    signals = strategy().generate(
        4,
        CandleWindow(candles(["100", "100", "100", "100", "100"]), 4),
        StrategyState(
            positions={"BTCUSDT": position},
            values={"symbol": "BTCUSDT", "entry_count": 2, "holding_candles": 5},
        ),
    )

    assert signals[0].side is Side.SELL
    assert signals[0].quantity == Decimal("2")
    assert signals[0].reason == "MAX_HOLDING"


def test_mean_reversion_signal_waits_until_position_has_minimum_profit():
    position = Position(
        symbol="BTCUSDT", quantity=Decimal("1"), average_price=Decimal("100")
    )

    signals = strategy().generate(
        2,
        CandleWindow(candles(["100", "99", "100.4"]), 2),
        StrategyState(
            positions={"BTCUSDT": position},
            values={"symbol": "BTCUSDT", "holding_candles": 1},
        ),
    )

    assert signals == []


def test_mean_reversion_does_not_read_future_candles():
    prefix = ["100", "100", "100", "90", "50"]
    first = strategy().generate(
        4, CandleWindow(candles(prefix + ["1000"]), 4), StrategyState()
    )
    second = strategy().generate(
        4, CandleWindow(candles(prefix + ["1"]), 4), StrategyState()
    )

    assert first == second
