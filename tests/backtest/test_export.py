import csv
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO

from quant_home.backtest.export import fills_to_csv
from quant_home.backtest.types import Fill


def test_fills_to_csv_exports_the_public_trade_columns():
    fills = (
        Fill.buy(
            "BTCUSDT",
            Decimal("0.125"),
            Decimal("64000.50"),
            Decimal("8.0000625"),
            filled_at=datetime(2025, 1, 1, tzinfo=UTC),
        ),
        Fill.sell("BTCUSDT", Decimal("0.125"), Decimal("65000"), Decimal("8.125")),
    )

    exported = fills_to_csv("trend", fills)

    assert list(csv.DictReader(StringIO(exported))) == [
        {
            "strategy": "trend",
            "symbol": "BTCUSDT",
            "side": "buy",
            "quantity": "0.125",
            "price": "64000.50",
            "fee": "8.0000625",
        },
        {
            "strategy": "trend",
            "symbol": "BTCUSDT",
            "side": "sell",
            "quantity": "0.125",
            "price": "65000",
            "fee": "8.125",
        },
    ]


def test_fills_to_csv_keeps_headers_when_there_are_no_fills():
    assert fills_to_csv("grid", ()) == "strategy,symbol,side,quantity,price,fee\r\n"
