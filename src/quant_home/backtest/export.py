import csv
from collections.abc import Sequence
from io import StringIO

from quant_home.backtest.types import Fill


CSV_COLUMNS = ("strategy", "symbol", "side", "quantity", "price", "fee")


def fills_to_csv(strategy: str, fills: Sequence[Fill]) -> str:
    """Return a portable CSV representation of a strategy's fills."""
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    for fill in fills:
        writer.writerow(
            {
                "strategy": strategy,
                "symbol": fill.symbol,
                "side": fill.side.value,
                "quantity": str(fill.quantity),
                "price": str(fill.price),
                "fee": str(fill.fee),
            }
        )
    return output.getvalue()
