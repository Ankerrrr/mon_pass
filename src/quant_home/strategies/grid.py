from dataclasses import dataclass
from decimal import Decimal

from quant_home.backtest.config import GridConfig
from quant_home.backtest.types import OrderIntent, OrderType, Side
from quant_home.market.candles import Candle
from quant_home.strategies.base import CandleWindow, StrategyState


@dataclass(frozen=True)
class GridCrossing:
    level: Decimal
    side: Side


def build_grid(config: GridConfig) -> tuple[Decimal, ...]:
    if config.spacing == "arithmetic":
        step = (config.upper_bound - config.lower_bound) / Decimal(config.grid_count)
        return tuple(
            config.lower_bound + step * Decimal(index)
            for index in range(config.grid_count + 1)
        )
    log_step = (config.upper_bound / config.lower_bound).ln() / Decimal(
        config.grid_count
    )
    values = [config.lower_bound]
    for index in range(1, config.grid_count):
        values.append(config.lower_bound * (log_step * Decimal(index)).exp())
    values.append(config.upper_bound)
    return tuple(values)


def crossed_levels(
    candle: Candle,
    levels: tuple[Decimal, ...],
) -> tuple[GridCrossing, ...]:
    path = (
        (candle.open, candle.low, candle.high, candle.close)
        if candle.close <= candle.open
        else (candle.open, candle.high, candle.low, candle.close)
    )
    result: list[GridCrossing] = []
    for start, end in zip(path, path[1:]):
        if end < start:
            crossed = sorted(
                (level for level in levels if end <= level < start), reverse=True
            )
            result.extend(GridCrossing(level, Side.BUY) for level in crossed)
        elif end > start:
            crossed = sorted(level for level in levels if start < level <= end)
            result.extend(GridCrossing(level, Side.SELL) for level in crossed)
    return tuple(result)


class GridStrategy:
    def __init__(self, config: GridConfig, symbol: str = "BTCUSDT") -> None:
        self.config = config
        self.symbol = symbol
        self.levels = build_grid(config)

    def generate(
        self,
        index: int,
        candles: CandleWindow,
        state: StrategyState,
    ) -> list[OrderIntent]:
        symbol = str(state.values.get("symbol", self.symbol))
        position = state.positions.get(symbol)
        quantity = position.quantity if position is not None else Decimal("0")
        current = candles.current

        if (
            position is not None
            and quantity > 0
            and current.close
            <= position.average_price * (Decimal("1") - self.config.stop_loss)
        ):
            return [self._market_sell(symbol, quantity, "STOP_LOSS")]

        outside = (
            current.close < self.config.lower_bound
            or current.close > self.config.upper_bound
        )
        if outside:
            if self.config.out_of_range_action == "close" and quantity > 0:
                return [self._market_sell(symbol, quantity, "OUT_OF_RANGE_CLOSE")]
            return []

        inventory_fraction = Decimal(state.values.get("inventory_fraction", "0"))
        sell_size = quantity / Decimal(self.config.grid_count) if quantity else Decimal("0")
        intents: list[OrderIntent] = []
        for crossing in crossed_levels(current, self.levels):
            if crossing.side is Side.BUY:
                if inventory_fraction >= self.config.maximum_inventory:
                    continue
                intents.append(
                    OrderIntent(
                        symbol=symbol,
                        side=Side.BUY,
                        order_type=OrderType.LIMIT,
                        reason="GRID_BUY",
                        allocation=self.config.capital_per_grid,
                        limit_price=crossing.level,
                    )
                )
                inventory_fraction += self.config.capital_per_grid
            elif sell_size > 0 and quantity >= sell_size:
                intents.append(
                    OrderIntent(
                        symbol=symbol,
                        side=Side.SELL,
                        order_type=OrderType.LIMIT,
                        reason="GRID_SELL",
                        quantity=sell_size,
                        limit_price=crossing.level,
                    )
                )
                quantity -= sell_size
        return intents

    @staticmethod
    def _market_sell(symbol: str, quantity: Decimal, reason: str) -> OrderIntent:
        return OrderIntent(
            symbol=symbol,
            side=Side.SELL,
            order_type=OrderType.MARKET,
            reason=reason,
            quantity=quantity,
        )
