from decimal import Decimal

from quant_home.backtest.types import Fill, Position, Side


class Ledger:
    def __init__(self, initial_cash: Decimal) -> None:
        if initial_cash <= 0:
            raise ValueError("initial cash must be positive")
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self._positions: dict[str, Position] = {}
        self._fills: list[Fill] = []

    @property
    def fills(self) -> tuple[Fill, ...]:
        return tuple(self._fills)

    def position(self, symbol: str) -> Position:
        return self._positions.get(
            symbol,
            Position(symbol=symbol, quantity=Decimal("0"), average_price=Decimal("0")),
        )

    def position_quantity(self, symbol: str) -> Decimal:
        return self.position(symbol).quantity

    def apply(self, fill: Fill) -> None:
        current = self.position(fill.symbol)
        notional = fill.quantity * fill.price
        if fill.side is Side.BUY:
            required_cash = notional + fill.fee
            if required_cash > self.cash:
                raise ValueError("fill requires more cash than the ledger owns")
            new_quantity = current.quantity + fill.quantity
            average_price = (
                current.quantity * current.average_price + notional
            ) / new_quantity
            new_cash = self.cash - required_cash
        else:
            if fill.quantity > current.quantity:
                raise ValueError("fill sells more inventory than the ledger owns")
            new_quantity = current.quantity - fill.quantity
            average_price = current.average_price if new_quantity else Decimal("0")
            new_cash = self.cash + notional - fill.fee

        if new_cash < 0 or new_quantity < 0:
            raise ValueError("fill would create a negative ledger balance")
        self.cash = new_cash
        self._positions[fill.symbol] = Position(
            symbol=fill.symbol,
            quantity=new_quantity,
            average_price=average_price,
        )
        self._fills.append(fill)

    def equity(self, prices: dict[str, Decimal]) -> Decimal:
        marked_positions = Decimal("0")
        for symbol, position in self._positions.items():
            if position.quantity and symbol not in prices:
                raise ValueError(f"missing mark price for {symbol}")
            marked_positions += position.quantity * prices.get(symbol, Decimal("0"))
        return self.cash + marked_positions
