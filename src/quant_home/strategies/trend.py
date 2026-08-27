from decimal import Decimal

from quant_home.backtest.config import TrendConfig
from quant_home.backtest.types import OrderIntent, OrderType, Side
from quant_home.strategies.base import CandleWindow, StrategyState


class TrendStrategy:
    def __init__(self, config: TrendConfig, symbol: str = "BTCUSDT") -> None:
        self.config = config
        self.symbol = symbol

    def generate(
        self,
        index: int,
        candles: CandleWindow,
        state: StrategyState,
    ) -> list[OrderIntent]:
        symbol = str(state.values.get("symbol", self.symbol))
        position = state.positions.get(symbol)
        closes = [candle.close for candle in candles]

        if position is not None and position.quantity > 0:
            exit_intent = self._exit_intent(symbol, closes, position, state)
            return [exit_intent] if exit_intent is not None else []

        last_exit_index = state.values.get("last_exit_index")
        if (
            isinstance(last_exit_index, int)
            and index - last_exit_index <= self.config.cooldown_candles
        ):
            return []
        if self._confirmed_cross_above(closes):
            return [
                OrderIntent.market_buy(
                    symbol=symbol,
                    reason="FAST_ABOVE_SLOW",
                    allocation=self.config.entry_allocation,
                )
            ]
        return []

    def _exit_intent(self, symbol, closes, position, state) -> OrderIntent | None:
        current = closes[-1]
        peak = Decimal(state.values.get("peak_price", max(closes)))
        stop_candidates = (
            (
                position.average_price * (Decimal("1") - self.config.fixed_stop_loss),
                "FIXED_STOP",
            ),
            (
                peak * (Decimal("1") - self.config.trailing_stop),
                "TRAILING_STOP",
            ),
        )
        stop_price, stop_reason = max(stop_candidates, key=lambda item: item[0])
        if current <= stop_price:
            return self._market_sell(symbol, position.quantity, stop_reason)
        if (
            self.config.take_profit is not None
            and current
            >= position.average_price * (Decimal("1") + self.config.take_profit)
        ):
            return self._market_sell(symbol, position.quantity, "TAKE_PROFIT")
        if self._crossed_below(closes):
            return self._market_sell(symbol, position.quantity, "FAST_BELOW_SLOW")
        return None

    @staticmethod
    def _market_sell(symbol: str, quantity: Decimal, reason: str) -> OrderIntent:
        return OrderIntent(
            symbol=symbol,
            side=Side.SELL,
            order_type=OrderType.MARKET,
            reason=reason,
            quantity=quantity,
        )

    def _confirmed_cross_above(self, closes: list[Decimal]) -> bool:
        fast = self._moving_average(closes, self.config.fast_period)
        slow = self._moving_average(closes, self.config.slow_period)
        start = len(closes) - self.config.confirmation_candles
        before = start - 1
        if before < 0 or fast[before] is None or slow[before] is None:
            return False
        if fast[before] > slow[before]:
            return False
        return all(
            fast[position] is not None
            and slow[position] is not None
            and fast[position] > slow[position]
            for position in range(start, len(closes))
        )

    def _crossed_below(self, closes: list[Decimal]) -> bool:
        fast = self._moving_average(closes, self.config.fast_period)
        slow = self._moving_average(closes, self.config.slow_period)
        if len(closes) < 2 or any(
            value is None for value in (fast[-2], slow[-2], fast[-1], slow[-1])
        ):
            return False
        return fast[-2] >= slow[-2] and fast[-1] < slow[-1]

    def _moving_average(
        self, values: list[Decimal], period: int
    ) -> list[Decimal | None]:
        if self.config.moving_average == "sma":
            return [
                None
                if index + 1 < period
                else sum(values[index + 1 - period : index + 1], Decimal("0"))
                / Decimal(period)
                for index in range(len(values))
            ]

        result: list[Decimal | None] = [None] * len(values)
        if len(values) < period:
            return result
        result[period - 1] = sum(values[:period], Decimal("0")) / Decimal(period)
        multiplier = Decimal("2") / Decimal(period + 1)
        for index in range(period, len(values)):
            previous = result[index - 1]
            result[index] = (values[index] - previous) * multiplier + previous
        return result
