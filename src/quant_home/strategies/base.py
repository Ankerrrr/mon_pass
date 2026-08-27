from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, overload

from quant_home.backtest.types import OrderIntent, Position
from quant_home.market.candles import Candle


@dataclass(frozen=True)
class CandleWindow(Sequence[Candle]):
    candles: tuple[Candle, ...]
    decision_index: int

    def __post_init__(self) -> None:
        if self.decision_index < 0 or self.decision_index >= len(self.candles):
            raise IndexError("decision_index is outside the candle series")

    def __len__(self) -> int:
        return self.decision_index + 1

    @overload
    def __getitem__(self, index: int) -> Candle: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[Candle, ...]: ...

    def __getitem__(self, index: int | slice) -> Candle | tuple[Candle, ...]:
        visible = self.candles[: self.decision_index + 1]
        return visible[index]

    def __iter__(self) -> Iterator[Candle]:
        return iter(self.candles[: self.decision_index + 1])

    @property
    def current(self) -> Candle:
        return self.candles[self.decision_index]


@dataclass(frozen=True)
class StrategyState:
    positions: dict[str, Position] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)


class Strategy(Protocol):
    def generate(
        self,
        index: int,
        candles: CandleWindow,
        state: StrategyState,
    ) -> list[OrderIntent]: ...
