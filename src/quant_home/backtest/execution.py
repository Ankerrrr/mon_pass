from decimal import Decimal

from quant_home.backtest.ledger import Ledger
from quant_home.backtest.types import Fill, OrderIntent, OrderType, Side
from quant_home.market.candles import Candle


class ExecutionModel:
    def __init__(self, fee_rate: Decimal, slippage_bps: Decimal) -> None:
        if fee_rate < 0 or fee_rate >= 1:
            raise ValueError("fee_rate must be between 0 and 1")
        if slippage_bps < 0:
            raise ValueError("slippage_bps cannot be negative")
        self.fee_rate = fee_rate
        self.slippage_bps = slippage_bps

    def fill(
        self,
        intent: OrderIntent,
        next_candle: Candle,
        ledger: Ledger,
    ) -> Fill | None:
        price = self._eligible_price(intent, next_candle)
        if price is None:
            return None
        quantity = self._quantity(intent, price, ledger)
        if quantity <= 0:
            return None
        fee = quantity * price * self.fee_rate
        if intent.side is Side.BUY and quantity * price + fee > ledger.cash:
            return None
        if intent.side is Side.SELL and quantity > ledger.position_quantity(intent.symbol):
            return None
        return Fill(
            symbol=intent.symbol,
            side=intent.side,
            quantity=quantity,
            price=price,
            fee=fee,
            filled_at=next_candle.open_time,
            reason=intent.reason,
        )

    def resolve_long_exit(
        self,
        symbol: str,
        quantity: Decimal,
        stop_price: Decimal,
        target_price: Decimal | None,
        next_candle: Candle,
    ) -> Fill | None:
        stop_touched = next_candle.low <= stop_price
        target_touched = target_price is not None and next_candle.high >= target_price
        if not stop_touched and not target_touched:
            return None

        if stop_touched:
            base_price = min(next_candle.open, stop_price)
            price = self._market_price(Side.SELL, base_price)
            reason = "STOP_LOSS"
        else:
            price = max(next_candle.open, target_price)
            reason = "TAKE_PROFIT"
        return Fill.sell(
            symbol,
            quantity,
            price,
            quantity * price * self.fee_rate,
            filled_at=next_candle.open_time,
            reason=reason,
        )

    def _eligible_price(self, intent: OrderIntent, candle: Candle) -> Decimal | None:
        if intent.order_type is OrderType.MARKET:
            return self._market_price(intent.side, candle.open)
        if intent.side is Side.BUY:
            if candle.low > intent.limit_price:
                return None
            return min(candle.open, intent.limit_price)
        if candle.high < intent.limit_price:
            return None
        return max(candle.open, intent.limit_price)

    def _market_price(self, side: Side, base_price: Decimal) -> Decimal:
        direction = Decimal("1") if side is Side.BUY else Decimal("-1")
        return base_price * (
            Decimal("1") + direction * self.slippage_bps / Decimal("10000")
        )

    def _quantity(self, intent: OrderIntent, price: Decimal, ledger: Ledger) -> Decimal:
        if intent.quantity is not None:
            return intent.quantity
        if intent.side is Side.BUY:
            budget = ledger.cash * intent.allocation
            return budget / (price * (Decimal("1") + self.fee_rate))
        return ledger.position_quantity(intent.symbol) * intent.allocation
