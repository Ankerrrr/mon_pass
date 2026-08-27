from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from math import sqrt
from statistics import stdev

from quant_home.backtest.types import EquityPoint, Fill, Side


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: Decimal
    annualized_return: Decimal
    max_drawdown: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    sharpe: float
    trade_count: int
    fees: Decimal


def calculate_metrics(
    equity_curve: Sequence[EquityPoint],
    fills: Sequence[Fill],
    *,
    annualization_periods: int = 365,
) -> PerformanceMetrics:
    """Calculate deterministic backtest metrics from equity and fill history."""
    if annualization_periods <= 0:
        raise ValueError("annualization_periods must be positive")

    total_return = _total_return(equity_curve)
    annualized_return = _annualized_return(
        equity_curve, total_return, annualization_periods
    )
    trade_pnls = _closed_trade_pnls(fills)
    gross_profit = sum((pnl for pnl in trade_pnls if pnl > 0), Decimal("0"))
    gross_loss = -sum((pnl for pnl in trade_pnls if pnl < 0), Decimal("0"))
    trade_count = len(trade_pnls)

    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        max_drawdown=_max_drawdown(equity_curve),
        win_rate=(
            Decimal(sum(pnl > 0 for pnl in trade_pnls)) / Decimal(trade_count)
            if trade_count
            else Decimal("0")
        ),
        profit_factor=(
            gross_profit / gross_loss
            if gross_loss
            else Decimal("Infinity") if gross_profit else Decimal("0")
        ),
        sharpe=_sharpe(equity_curve, annualization_periods),
        trade_count=trade_count,
        fees=sum((fill.fee for fill in fills), Decimal("0")),
    )


def _total_return(equity_curve: Sequence[EquityPoint]) -> Decimal:
    if len(equity_curve) < 2 or equity_curve[0].equity == 0:
        return Decimal("0")
    return equity_curve[-1].equity / equity_curve[0].equity - Decimal("1")


def _annualized_return(
    equity_curve: Sequence[EquityPoint],
    total_return: Decimal,
    annualization_periods: int,
) -> Decimal:
    periods = len(equity_curve) - 1
    if periods <= 0 or equity_curve[0].equity == 0:
        return Decimal("0")
    ratio = Decimal("1") + total_return
    if ratio == 0:
        return Decimal("-1")
    exponent = Decimal(annualization_periods) / Decimal(periods)
    return ratio**exponent - Decimal("1")


def _max_drawdown(equity_curve: Sequence[EquityPoint]) -> Decimal:
    peak = Decimal("0")
    maximum = Decimal("0")
    for point in equity_curve:
        peak = max(peak, point.equity)
        if peak:
            maximum = max(maximum, (peak - point.equity) / peak)
    return maximum


def _sharpe(
    equity_curve: Sequence[EquityPoint], annualization_periods: int
) -> float:
    returns = [
        float(current.equity / previous.equity - Decimal("1"))
        for previous, current in zip(equity_curve, equity_curve[1:])
        if previous.equity
    ]
    if len(returns) < 2:
        return 0.0
    volatility = stdev(returns)
    if volatility == 0:
        return 0.0
    return (sum(returns) / len(returns)) / volatility * sqrt(annualization_periods)


def _closed_trade_pnls(fills: Sequence[Fill]) -> tuple[Decimal, ...]:
    inventory: dict[str, tuple[Decimal, Decimal]] = {}
    pnls: list[Decimal] = []
    for fill in fills:
        quantity, cost = inventory.get(fill.symbol, (Decimal("0"), Decimal("0")))
        if fill.side is Side.BUY:
            inventory[fill.symbol] = (
                quantity + fill.quantity,
                cost + fill.quantity * fill.price + fill.fee,
            )
            continue
        if fill.quantity > quantity:
            raise ValueError(f"sell fill exceeds inventory for {fill.symbol}")
        allocated_cost = cost * fill.quantity / quantity
        proceeds = fill.quantity * fill.price - fill.fee
        pnls.append(proceeds - allocated_cost)
        remaining_quantity = quantity - fill.quantity
        inventory[fill.symbol] = (
            remaining_quantity,
            cost - allocated_cost if remaining_quantity else Decimal("0"),
        )
    return tuple(pnls)
