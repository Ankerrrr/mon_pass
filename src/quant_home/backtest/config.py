from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from quant_home.market.candles import CandleInterval


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class AllocationConfig(FrozenModel):
    trend: Decimal = Field(default=Decimal("0.40"), ge=0, le=1)
    mean_reversion: Decimal = Field(default=Decimal("0.30"), ge=0, le=1)
    grid: Decimal = Field(default=Decimal("0.20"), ge=0, le=1)
    cash_reserve: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)

    @model_validator(mode="after")
    def total_is_one(self):
        if sum((self.trend, self.mean_reversion, self.grid, self.cash_reserve)) != Decimal("1"):
            raise ValueError("strategy allocations and cash reserve must total 1")
        return self


class SymbolWeight(FrozenModel):
    symbol: str = Field(min_length=5, max_length=20, pattern=r"^[A-Z0-9]+$")
    weight: Decimal = Field(gt=0, le=1)


class StrategyUniverse(FrozenModel):
    interval: CandleInterval
    symbols: tuple[SymbolWeight, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def symbols_are_unique_and_weighted(self):
        names = [item.symbol for item in self.symbols]
        if len(names) != len(set(names)):
            raise ValueError("strategy symbols must be unique")
        if sum((item.weight for item in self.symbols), Decimal("0")) != Decimal("1"):
            raise ValueError("strategy symbol weights must total 1")
        return self


class TrendConfig(FrozenModel):
    moving_average: Literal["ema", "sma"] = "ema"
    fast_period: int = Field(default=20, ge=2, le=500)
    slow_period: int = Field(default=50, ge=3, le=1000)
    confirmation_candles: int = Field(default=1, ge=1, le=20)
    fixed_stop_loss: Decimal = Field(default=Decimal("0.03"), gt=0, lt=1)
    trailing_stop: Decimal = Field(default=Decimal("0.05"), gt=0, lt=1)
    take_profit: Decimal | None = Field(default=None, gt=0, lt=10)
    entry_allocation: Decimal = Field(default=Decimal("1"), gt=0, le=1)
    cooldown_candles: int = Field(default=0, ge=0, le=10000)

    @model_validator(mode="after")
    def fast_is_less_than_slow(self):
        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be less than slow_period")
        return self


class MeanReversionConfig(FrozenModel):
    rsi_period: int = Field(default=14, ge=2, le=500)
    rsi_entry: Decimal = Field(default=Decimal("30"), ge=0, le=100)
    rsi_exit: Decimal = Field(default=Decimal("55"), ge=0, le=100)
    bollinger_period: int = Field(default=20, ge=2, le=1000)
    bollinger_stddev: Decimal = Field(default=Decimal("2"), gt=0, le=10)
    staged_entries: int = Field(default=3, ge=1, le=20)
    staged_entry_distance: Decimal = Field(default=Decimal("0.02"), gt=0, lt=1)
    max_holding_candles: int = Field(default=72, ge=1, le=100000)
    stop_loss: Decimal = Field(default=Decimal("0.05"), gt=0, lt=1)
    take_profit: Decimal = Field(default=Decimal("0.08"), gt=0, lt=10)

    @model_validator(mode="after")
    def entry_is_less_than_exit(self):
        if self.rsi_entry >= self.rsi_exit:
            raise ValueError("rsi_entry must be less than rsi_exit")
        return self


class GridConfig(FrozenModel):
    lower_bound: Decimal = Field(default=Decimal("0.90"), gt=0)
    upper_bound: Decimal = Field(default=Decimal("1.10"), gt=0)
    grid_count: int = Field(default=10, ge=2, le=500)
    spacing: Literal["arithmetic", "geometric"] = "arithmetic"
    capital_per_grid: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    maximum_inventory: Decimal = Field(default=Decimal("0.80"), gt=0, le=1)
    out_of_range_action: Literal["stop_entries", "close", "recalculate"] = "stop_entries"
    stop_loss: Decimal = Field(default=Decimal("0.10"), gt=0, lt=1)
    regrid_cooldown_candles: int = Field(default=0, ge=0, le=100000)

    @model_validator(mode="after")
    def lower_is_less_than_upper(self):
        if self.lower_bound >= self.upper_bound:
            raise ValueError("lower_bound must be less than upper_bound")
        return self


class BacktestConfig(FrozenModel):
    initial_capital: Decimal = Field(default=Decimal("10000"), gt=0)
    start_time: datetime
    end_time: datetime
    allocations: AllocationConfig = Field(default_factory=AllocationConfig)
    universes: dict[Literal["trend", "mean_reversion", "grid"], StrategyUniverse]
    trend: TrendConfig = Field(default_factory=TrendConfig)
    mean_reversion: MeanReversionConfig = Field(default_factory=MeanReversionConfig)
    grid: GridConfig = Field(default_factory=GridConfig)
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0, lt=1)
    slippage_bps: Decimal = Field(default=Decimal("5"), ge=0, le=10000)

    @model_validator(mode="before")
    @classmethod
    def apply_default_intervals(cls, value: Any):
        if not isinstance(value, dict) or not isinstance(value.get("universes"), dict):
            return value
        result = dict(value)
        universes = {name: dict(universe) for name, universe in value["universes"].items()}
        defaults = {
            "trend": CandleInterval.FOUR_HOURS,
            "mean_reversion": CandleInterval.ONE_HOUR,
            "grid": CandleInterval.FIFTEEN_MINUTES,
        }
        for name, interval in defaults.items():
            if name in universes:
                universes[name].setdefault("interval", interval)
        result["universes"] = universes
        return result

    @field_validator("start_time", "end_time")
    @classmethod
    def timestamps_are_utc(cls, value: datetime):
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("timestamps must use UTC")
        return value

    @model_validator(mode="after")
    def range_and_universes_are_complete(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        required = {"trend", "mean_reversion", "grid"}
        if set(self.universes) != required:
            raise ValueError("universes must contain trend, mean_reversion, and grid")
        return self
