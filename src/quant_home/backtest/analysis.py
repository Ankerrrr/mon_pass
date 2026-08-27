from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any, Iterable

from quant_home.backtest.types import Fill, Side


ZERO = Decimal("0")


def _text(value: Decimal) -> str:
    return str(value)


def analyze_ledger(
    initial_cash: Decimal,
    fills: Iterable[Fill],
    final_prices: dict[str, Decimal] | None = None,
) -> dict[str, Any]:
    """Replay fills into an auditable P&L summary and operation history."""
    cash = initial_cash
    quantities: dict[str, Decimal] = {}
    costs: dict[str, Decimal] = {}
    marks: dict[str, Decimal] = {}
    realized = ZERO
    fees = ZERO
    previous_equity = initial_cash
    operations: list[dict[str, Any]] = []

    for fill in fills:
        symbol = fill.symbol
        quantity_before = quantities.get(symbol, ZERO)
        cost_before = costs.get(symbol, ZERO)
        notional = fill.quantity * fill.price
        marks[symbol] = fill.price
        fees += fill.fee

        if fill.side is Side.BUY:
            cash_delta = -(notional + fill.fee)
            quantities[symbol] = quantity_before + fill.quantity
            costs[symbol] = cost_before + notional + fill.fee
            operation_realized = ZERO
        else:
            allocated_cost = (
                cost_before * fill.quantity / quantity_before
                if quantity_before else ZERO
            )
            cash_delta = notional - fill.fee
            operation_realized = cash_delta - allocated_cost
            quantities[symbol] = quantity_before - fill.quantity
            costs[symbol] = cost_before - allocated_cost
            realized += operation_realized

        cash += cash_delta
        equity = cash + sum(
            quantity * marks.get(name, ZERO)
            for name, quantity in quantities.items()
        )
        operations.append(
            {
                "filled_at": fill.filled_at.isoformat() if fill.filled_at else None,
                "symbol": symbol,
                "side": fill.side.value,
                "quantity": _text(fill.quantity),
                "price": _text(fill.price),
                "notional": _text(notional),
                "fee": _text(fill.fee),
                "cash_delta": _text(cash_delta),
                "realized_pnl": _text(operation_realized),
                "cash_after": _text(cash),
                "position_quantity_after": _text(quantities[symbol]),
                "equity_after": _text(equity),
                "equity_change": _text(equity - previous_equity),
                "reason": fill.reason,
                "mode": fill.mode.value,
            }
        )
        previous_equity = equity

    supplied_prices = final_prices or {}
    open_symbols = [name for name, quantity in quantities.items() if quantity]
    valuation_is_estimated = any(name not in supplied_prices for name in open_symbols)
    position_value = sum(
        quantities[name] * supplied_prices.get(name, marks.get(name, ZERO))
        for name in open_symbols
    )
    open_cost = sum(costs[name] for name in open_symbols)
    ending_equity = cash + position_value
    total_pnl = ending_equity - initial_cash

    return {
        "summary": {
            "initial_cash": _text(initial_cash),
            "ending_cash": _text(cash),
            "position_value": _text(position_value),
            "ending_equity": _text(ending_equity),
            "total_pnl": _text(total_pnl),
            "total_return": _text(total_pnl / initial_cash if initial_cash else ZERO),
            "realized_pnl": _text(realized),
            "unrealized_pnl": _text(position_value - open_cost),
            "fees": _text(fees),
            "fill_count": len(operations),
            "valuation_is_estimated": valuation_is_estimated,
        },
        "operations": operations,
    }


def enrich_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Add analysis to both new and historical JSON ledger snapshots."""
    enriched = deepcopy(snapshot)
    final_prices = enriched.get("final_prices") or enriched.get("last_prices", {})
    for strategy, ledger in enriched.get("ledgers", {}).items():
        analysis = analyze_ledger(
            Decimal(ledger["initial_cash"]),
            (Fill.model_validate(row) for row in ledger.get("fills", [])),
            {
                symbol: Decimal(price)
                for symbol, price in final_prices.get(strategy, {}).items()
            },
        )
        ledger.update(analysis)
    return enriched
