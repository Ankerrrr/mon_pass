from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant_home.backtest.execution import ExecutionModel
from quant_home.backtest.ledger import Ledger
from quant_home.backtest.types import OrderIntent, OrderType, Side
from quant_home.market.candles import Candle


def candle(open_: str, high: str, low: str, close: str = "100") -> Candle:
    opened = datetime(2025, 1, 1, tzinfo=UTC)
    return Candle(
        open_time=opened,
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("1"),
        close_time=opened + timedelta(hours=1),
    )


def test_market_buy_fills_at_next_open_with_slippage_and_fee():
    ledger = Ledger(initial_cash=Decimal("1000"))
    model = ExecutionModel(fee_rate=Decimal("0.001"), slippage_bps=Decimal("10"))
    intent = OrderIntent.market_buy("BTCUSDT", "ENTRY", Decimal("0.50"))

    fill = model.fill(intent, candle("100", "105", "95"), ledger)

    assert fill is not None
    assert fill.price == Decimal("100.100")
    assert fill.fee == fill.quantity * fill.price * Decimal("0.001")
    assert fill.quantity * fill.price + fill.fee == Decimal("500.0")


def test_limit_order_requires_the_next_candle_to_cross_price():
    ledger = Ledger(initial_cash=Decimal("1000"))
    model = ExecutionModel(fee_rate=Decimal("0"), slippage_bps=Decimal("0"))
    intent = OrderIntent(
        symbol="BTCUSDT",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        reason="GRID_BUY",
        allocation=Decimal("0.10"),
        limit_price=Decimal("90"),
    )

    assert model.fill(intent, candle("100", "105", "91"), ledger) is None
    crossed = model.fill(intent, candle("100", "105", "89"), ledger)
    assert crossed is not None
    assert crossed.price == Decimal("90")


def test_stop_and_target_same_candle_uses_adverse_stop_first():
    model = ExecutionModel(fee_rate=Decimal("0"), slippage_bps=Decimal("0"))

    fill = model.resolve_long_exit(
        symbol="BTCUSDT",
        quantity=Decimal("1"),
        stop_price=Decimal("95"),
        target_price=Decimal("110"),
        next_candle=candle("100", "111", "94"),
    )

    assert fill is not None
    assert fill.side is Side.SELL
    assert fill.price == Decimal("95")
    assert fill.reason == "STOP_LOSS"


def test_gap_through_stop_fills_at_worse_open_price():
    model = ExecutionModel(fee_rate=Decimal("0"), slippage_bps=Decimal("0"))

    fill = model.resolve_long_exit(
        symbol="BTCUSDT",
        quantity=Decimal("1"),
        stop_price=Decimal("95"),
        target_price=Decimal("110"),
        next_candle=candle("90", "96", "89"),
    )

    assert fill is not None
    assert fill.price == Decimal("90")
