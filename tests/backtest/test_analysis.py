from datetime import UTC, datetime
from decimal import Decimal

from quant_home.backtest.analysis import analyze_ledger
from quant_home.backtest.types import Fill


def test_analyze_ledger_reports_profit_and_per_operation_asset_changes() -> None:
    fills = [
        Fill.buy(
            "BTCUSDT", Decimal("2"), Decimal("100"), Decimal("2"),
            filled_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
        Fill.sell(
            "BTCUSDT", Decimal("1"), Decimal("120"), Decimal("1"),
            filled_at=datetime(2026, 1, 2, tzinfo=UTC),
        ),
    ]

    result = analyze_ledger(Decimal("1000"), fills, {"BTCUSDT": Decimal("130")})

    assert result["summary"] == {
        "initial_cash": "1000",
        "ending_cash": "917",
        "position_value": "130",
        "ending_equity": "1047",
        "total_pnl": "47",
        "total_return": "0.047",
        "realized_pnl": "18",
        "unrealized_pnl": "29",
        "fees": "3",
        "fill_count": 2,
        "valuation_is_estimated": False,
    }
    assert result["operations"][0]["cash_delta"] == "-202"
    assert result["operations"][0]["equity_change"] == "-2"
    assert result["operations"][1]["cash_delta"] == "119"
    assert result["operations"][1]["realized_pnl"] == "18"
    assert result["operations"][1]["equity_after"] == "1037"
    assert result["operations"][1]["equity_change"] == "39"


def test_analyze_ledger_marks_open_position_estimate_without_final_price() -> None:
    fills = [Fill.buy("BTCUSDT", Decimal("1"), Decimal("100"), Decimal("1"))]

    result = analyze_ledger(Decimal("1000"), fills)

    assert result["summary"]["ending_equity"] == "999"
    assert result["summary"]["valuation_is_estimated"] is True
