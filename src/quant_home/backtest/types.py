from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class StrategyKind(StrEnum):
    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    GRID = "grid"


class TradingMode(StrEnum):
    BACKTEST = "backtest"
    PAPER = "paper"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class OrderIntent(FrozenModel):
    symbol: str = Field(min_length=5, max_length=20, pattern=r"^[A-Z0-9]+$")
    side: Side
    order_type: OrderType = OrderType.MARKET
    reason: str = Field(min_length=1, max_length=120)
    allocation: Decimal | None = Field(default=None, gt=0, le=1)
    quantity: Decimal | None = Field(default=None, gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def sizing_and_price_are_valid(self):
        if self.allocation is None and self.quantity is None:
            raise ValueError("allocation or quantity is required")
        if self.order_type is OrderType.LIMIT and self.limit_price is None:
            raise ValueError("limit_price is required for limit orders")
        if self.order_type is OrderType.MARKET and self.limit_price is not None:
            raise ValueError("limit_price is not allowed for market orders")
        return self

    @classmethod
    def market_buy(cls, symbol: str, reason: str, allocation: Decimal):
        return cls(
            symbol=symbol,
            side=Side.BUY,
            order_type=OrderType.MARKET,
            reason=reason,
            allocation=allocation,
        )


class Fill(FrozenModel):
    symbol: str
    side: Side
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    fee: Decimal = Field(ge=0)
    filled_at: datetime | None = None
    reason: str = ""
    mode: TradingMode = TradingMode.BACKTEST

    @classmethod
    def buy(cls, symbol: str, quantity: Decimal, price: Decimal, fee: Decimal, **values):
        return cls(symbol=symbol, side=Side.BUY, quantity=quantity, price=price, fee=fee, **values)

    @classmethod
    def sell(cls, symbol: str, quantity: Decimal, price: Decimal, fee: Decimal, **values):
        return cls(symbol=symbol, side=Side.SELL, quantity=quantity, price=price, fee=fee, **values)


class Position(FrozenModel):
    symbol: str
    quantity: Decimal = Field(ge=0)
    average_price: Decimal = Field(ge=0)


class EquityPoint(FrozenModel):
    timestamp: datetime
    equity: Decimal = Field(ge=0)
    cash: Decimal = Field(ge=0)
    exposure: Decimal = Field(ge=0)


class StrategySignal(FrozenModel):
    index: int = Field(ge=0)
    intent: OrderIntent
