from dataclasses import dataclass

from quant_home.market.candles import Candle, CandleInterval


@dataclass(frozen=True)
class StreamSubscription:
    symbol: str
    interval: CandleInterval


@dataclass(frozen=True)
class CandleClosed:
    symbol: str
    interval: CandleInterval
    candle: Candle


class ReconnectPolicy:
    def __init__(self, base_delay: float = 0.5, maximum_delay: float = 30.0) -> None:
        self.base_delay = base_delay
        self.maximum_delay = maximum_delay

    def next_delay(self, attempt: int) -> float:
        return min(self.maximum_delay, self.base_delay * (2 ** max(0, attempt)))
