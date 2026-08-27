from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from quant_home.backtest.types import OrderIntent, Side


class RiskReason(StrEnum):
    SYMBOL_EXPOSURE = "SYMBOL_EXPOSURE"
    STRATEGY_EXPOSURE = "STRATEGY_EXPOSURE"
    TOTAL_EXPOSURE = "TOTAL_EXPOSURE"
    DAILY_LOSS = "DAILY_LOSS"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class RiskLimits(FrozenModel):
    max_symbol_exposure: Decimal = Field(default=Decimal("0.25"), gt=0, le=1)
    max_strategy_exposure: Decimal = Field(default=Decimal("0.90"), gt=0, le=1)
    max_total_exposure: Decimal = Field(default=Decimal("0.90"), gt=0, le=1)
    max_daily_loss: Decimal = Field(default=Decimal("0.15"), gt=0, le=1)
    max_drawdown: Decimal = Field(default=Decimal("0.25"), gt=0, le=1)


class RiskContext(FrozenModel):
    equity: Decimal = Field(gt=0)
    peak_equity: Decimal = Field(gt=0)
    daily_start_equity: Decimal = Field(gt=0)
    total_exposure: Decimal = Field(ge=0)
    strategy_exposure: Decimal = Field(ge=0)
    symbol_exposure: Decimal = Field(ge=0)
    requested_exposure: Decimal = Field(ge=0)
    available_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    requested_quantity: Decimal | None = Field(default=None, gt=0)


class RiskDecision(FrozenModel):
    allowed: bool
    adjusted_quantity: Decimal = Field(ge=0)
    reason: RiskReason | None = None


class RiskManager:
    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits

    def evaluate(self, intent: OrderIntent, context: RiskContext) -> RiskDecision:
        requested_quantity = (
            intent.quantity
            or context.requested_quantity
            or context.available_quantity * (intent.allocation or Decimal("0"))
        )
        if intent.side is Side.SELL:
            return RiskDecision(
                allowed=True,
                adjusted_quantity=min(requested_quantity, context.available_quantity),
            )

        drawdown = max(
            Decimal("0"),
            (context.peak_equity - context.equity) / context.peak_equity,
        )
        if drawdown >= self.limits.max_drawdown:
            return self._rejected(RiskReason.MAX_DRAWDOWN)

        daily_loss = max(
            Decimal("0"),
            (context.daily_start_equity - context.equity) / context.daily_start_equity,
        )
        if daily_loss >= self.limits.max_daily_loss:
            return self._rejected(RiskReason.DAILY_LOSS)

        capacities = (
            (
                self.limits.max_symbol_exposure - context.symbol_exposure,
                RiskReason.SYMBOL_EXPOSURE,
            ),
            (
                self.limits.max_strategy_exposure - context.strategy_exposure,
                RiskReason.STRATEGY_EXPOSURE,
            ),
            (
                self.limits.max_total_exposure - context.total_exposure,
                RiskReason.TOTAL_EXPOSURE,
            ),
        )
        capacity, reason = min(capacities, key=lambda item: item[0])
        if capacity <= 0:
            return self._rejected(reason)
        if context.requested_exposure > capacity:
            adjusted = requested_quantity * capacity / context.requested_exposure
            return RiskDecision(
                allowed=adjusted > 0,
                adjusted_quantity=adjusted,
                reason=reason,
            )
        return RiskDecision(allowed=True, adjusted_quantity=requested_quantity)

    @staticmethod
    def _rejected(reason: RiskReason) -> RiskDecision:
        return RiskDecision(
            allowed=False,
            adjusted_quantity=Decimal("0"),
            reason=reason,
        )
