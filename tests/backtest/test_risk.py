from decimal import Decimal

from quant_home.backtest.risk import (
    RiskContext,
    RiskLimits,
    RiskManager,
    RiskReason,
)
from quant_home.backtest.types import OrderIntent, OrderType, Side


def buy_intent(quantity: str = "2") -> OrderIntent:
    return OrderIntent(
        symbol="BTCUSDT",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        reason="ENTRY",
        quantity=Decimal(quantity),
    )


def sell_intent(quantity: str = "1") -> OrderIntent:
    return OrderIntent(
        symbol="BTCUSDT",
        side=Side.SELL,
        order_type=OrderType.MARKET,
        reason="EXIT",
        quantity=Decimal(quantity),
    )


def context(**changes) -> RiskContext:
    values = {
        "equity": Decimal("800"),
        "peak_equity": Decimal("1000"),
        "daily_start_equity": Decimal("900"),
        "total_exposure": Decimal("0.40"),
        "strategy_exposure": Decimal("0.20"),
        "symbol_exposure": Decimal("0.10"),
        "requested_exposure": Decimal("0.05"),
        "available_quantity": Decimal("2"),
    }
    values.update(changes)
    return RiskContext(**values)


def test_entry_is_rejected_after_drawdown_stop():
    manager = RiskManager(RiskLimits(max_drawdown=Decimal("0.19")))

    decision = manager.evaluate(buy_intent(), context())

    assert decision.allowed is False
    assert decision.reason is RiskReason.MAX_DRAWDOWN


def test_exit_is_allowed_when_entries_are_stopped():
    manager = RiskManager(
        RiskLimits(max_drawdown=Decimal("0.10"), max_daily_loss=Decimal("0.05"))
    )

    decision = manager.evaluate(sell_intent(), context())

    assert decision.allowed is True
    assert decision.adjusted_quantity == Decimal("1")
    assert decision.reason is None


def test_symbol_limit_reduces_entry_quantity_to_remaining_capacity():
    manager = RiskManager(RiskLimits(max_symbol_exposure=Decimal("0.12")))

    decision = manager.evaluate(
        buy_intent("10"),
        context(
            symbol_exposure=Decimal("0.10"),
            requested_exposure=Decimal("0.05"),
        ),
    )

    assert decision.allowed is True
    assert decision.adjusted_quantity == Decimal("4")
    assert decision.reason is RiskReason.SYMBOL_EXPOSURE


def test_entry_is_rejected_when_total_exposure_has_no_capacity():
    manager = RiskManager(RiskLimits(max_total_exposure=Decimal("0.80")))

    decision = manager.evaluate(
        buy_intent(),
        context(total_exposure=Decimal("0.80")),
    )

    assert decision.allowed is False
    assert decision.adjusted_quantity == 0
    assert decision.reason is RiskReason.TOTAL_EXPOSURE
