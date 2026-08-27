from decimal import Decimal

import pytest

from quant_home.backtest.ledger import Ledger
from quant_home.backtest.types import Fill


def test_zero_cash_ledger_supports_a_disabled_strategy():
    ledger = Ledger(initial_cash=Decimal("0"))

    assert ledger.cash == 0
    assert ledger.equity({}) == 0


def test_round_trip_conserves_cash_after_fee():
    ledger = Ledger(initial_cash=Decimal("1000"))

    ledger.apply(Fill.buy("BTCUSDT", Decimal("1"), Decimal("100"), Decimal("0.10")))
    ledger.apply(Fill.sell("BTCUSDT", Decimal("1"), Decimal("110"), Decimal("0.11")))

    assert ledger.cash == Decimal("1009.79")
    assert ledger.position_quantity("BTCUSDT") == 0


def test_rejected_fill_does_not_mutate_ledger():
    ledger = Ledger(initial_cash=Decimal("100"))

    with pytest.raises(ValueError, match="cash"):
        ledger.apply(Fill.buy("BTCUSDT", Decimal("2"), Decimal("100"), Decimal("0")))

    assert ledger.cash == Decimal("100")
    assert ledger.position_quantity("BTCUSDT") == 0
    assert ledger.fills == ()


def test_average_price_and_mark_to_market_are_exact_decimals():
    ledger = Ledger(initial_cash=Decimal("1000"))
    ledger.apply(Fill.buy("BTCUSDT", Decimal("1"), Decimal("100"), Decimal("0")))
    ledger.apply(Fill.buy("BTCUSDT", Decimal("1"), Decimal("120"), Decimal("0")))

    assert ledger.position("BTCUSDT").average_price == Decimal("110")
    assert ledger.equity({"BTCUSDT": Decimal("130")}) == Decimal("1040")

    with pytest.raises(ValueError, match="inventory"):
        ledger.apply(Fill.sell("BTCUSDT", Decimal("3"), Decimal("130"), Decimal("0")))
    assert ledger.position_quantity("BTCUSDT") == Decimal("2")
