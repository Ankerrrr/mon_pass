from decimal import Decimal

from quant_home.backtest.config import MeanReversionConfig
from quant_home.backtest.types import OrderIntent, OrderType, Side
from quant_home.strategies.base import CandleWindow, StrategyState


class MeanReversionStrategy:
    def __init__(
        self,
        config: MeanReversionConfig,
        symbol: str = "BTCUSDT",
    ) -> None:
        self.config = config
        self.symbol = symbol

    def generate(
        self,
        index: int,
        candles: CandleWindow,
        state: StrategyState,
    ) -> list[OrderIntent]:
        symbol = str(state.values.get("symbol", self.symbol))
        closes = [candle.close for candle in candles]
        current = closes[-1]
        rsi = self._rsi(closes)
        lower_band, middle_band = self._bollinger(closes)
        if rsi is None or lower_band is None:
            return []

        position = state.positions.get(symbol)
        if position is not None and position.quantity > 0:
            exit_reason = self._exit_reason(
                current=current,
                rsi=rsi,
                middle_band=middle_band,
                average_price=position.average_price,
                holding_candles=int(state.values.get("holding_candles", 0)),
            )
            if exit_reason is not None:
                return [self._market_sell(symbol, position.quantity, exit_reason)]

        entry_ready = rsi < self.config.rsi_entry and current <= lower_band
        if not entry_ready:
            return []
        entry_count = int(state.values.get("entry_count", 0))
        if entry_count >= self.config.staged_entries:
            return []
        if entry_count:
            last_entry = Decimal(state.values["last_entry_price"])
            required_price = last_entry * (
                Decimal("1") - self.config.staged_entry_distance
            )
            if current > required_price:
                return []
            reason = "STAGED_ENTRY"
        else:
            reason = "RSI_AND_LOWER_BAND"
        return [
            OrderIntent.market_buy(
                symbol=symbol,
                reason=reason,
                allocation=Decimal("1") / Decimal(self.config.staged_entries),
            )
        ]

    def _exit_reason(
        self,
        current: Decimal,
        rsi: Decimal,
        middle_band: Decimal,
        average_price: Decimal,
        holding_candles: int,
    ) -> str | None:
        if current <= average_price * (Decimal("1") - self.config.stop_loss):
            return "STOP_LOSS"
        if current >= average_price * (Decimal("1") + self.config.take_profit):
            return "TAKE_PROFIT"
        if holding_candles >= self.config.max_holding_candles:
            return "MAX_HOLDING"
        minimum_profitable_exit = average_price * (
            Decimal("1") + self.config.minimum_exit_profit
        )
        if (
            rsi > self.config.rsi_exit or current >= middle_band
        ) and current >= minimum_profitable_exit:
            return "MEAN_REVERSION_EXIT"
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

    def _rsi(self, closes: list[Decimal]) -> Decimal | None:
        if len(closes) <= self.config.rsi_period:
            return None
        changes = [
            closes[index] - closes[index - 1]
            for index in range(len(closes) - self.config.rsi_period, len(closes))
        ]
        gains = sum((max(change, Decimal("0")) for change in changes), Decimal("0"))
        losses = sum((max(-change, Decimal("0")) for change in changes), Decimal("0"))
        if losses == 0:
            return Decimal("100") if gains else Decimal("50")
        relative_strength = gains / losses
        return Decimal("100") - Decimal("100") / (Decimal("1") + relative_strength)

    def _bollinger(
        self, closes: list[Decimal]
    ) -> tuple[Decimal | None, Decimal | None]:
        if len(closes) < self.config.bollinger_period:
            return None, None
        values = closes[-self.config.bollinger_period :]
        mean = sum(values, Decimal("0")) / Decimal(len(values))
        variance = sum(((value - mean) ** 2 for value in values), Decimal("0")) / Decimal(len(values))
        standard_deviation = variance.sqrt()
        lower = mean - standard_deviation * self.config.bollinger_stddev
        return lower, mean
