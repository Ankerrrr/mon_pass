from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from quant_home.backtest.types import OrderIntent, OrderType, Side
from quant_home.market.candles import Candle
from quant_home.strategies.base import CandleWindow


def candle(hour: int, close: str) -> Candle:
    opened = datetime(2025, 1, 1, hour, tzinfo=UTC)
    return Candle(
        open_time=opened,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("1"),
        close_time=opened + timedelta(hours=1),
    )


def test_market_intent_is_frozen_and_carries_allocation():
    intent = OrderIntent.market_buy(
        symbol="BTCUSDT",
        reason="FAST_ABOVE_SLOW",
        allocation=Decimal("0.25"),
    )

    assert intent.side is Side.BUY
    assert intent.order_type is OrderType.MARKET
    assert intent.allocation == Decimal("0.25")
    with pytest.raises(ValidationError):
        intent.reason = "CHANGED"


def test_limit_intent_requires_a_positive_limit_price():
    with pytest.raises(ValidationError, match="limit_price"):
        OrderIntent(
            symbol="BTCUSDT",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            reason="GRID_LEVEL",
            allocation=Decimal("0.10"),
        )


def test_candle_window_cannot_reveal_future_candles():
    candles = (candle(0, "100"), candle(1, "101"), candle(2, "999"))
    window = CandleWindow(candles=candles, decision_index=1)

    assert len(window) == 2
    assert window.current.close == Decimal("101")
    assert [item.close for item in window] == [Decimal("100"), Decimal("101")]
    with pytest.raises(IndexError):
        _ = window[2]
