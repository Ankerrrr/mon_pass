from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json

from quant_home.backtest.config import BacktestConfig
from quant_home.backtest.execution import ExecutionModel
from quant_home.backtest.ledger import Ledger
from quant_home.backtest.types import Fill, Side, StrategyKind
from quant_home.market.candles import Candle
from quant_home.strategies.base import CandleWindow, Strategy, StrategyState
from quant_home.strategies.grid import GridStrategy
from quant_home.strategies.mean_reversion import MeanReversionStrategy
from quant_home.strategies.trend import TrendStrategy


StrategyFactory = Callable[[BacktestConfig, str], Strategy]


@dataclass(frozen=True)
class BacktestResult:
    ledgers: dict[StrategyKind, Ledger]
    cash_reserve: Decimal
    fingerprint: str
    engine_version: str
    final_prices: dict[StrategyKind, dict[str, Decimal]] = field(default_factory=dict)


class BacktestEngine:
    VERSION = "3"

    def __init__(
        self,
        strategy_factory: dict[StrategyKind, StrategyFactory] | None = None,
    ) -> None:
        self.strategy_factory = strategy_factory or {
            StrategyKind.TREND: lambda config, symbol: TrendStrategy(
                config.trend, symbol
            ),
            StrategyKind.MEAN_REVERSION: lambda config, symbol: MeanReversionStrategy(
                config.mean_reversion, symbol
            ),
            StrategyKind.GRID: lambda config, symbol: GridStrategy(config.grid, symbol),
        }

    def run(
        self,
        config: BacktestConfig,
        datasets: dict[StrategyKind, dict[str, tuple[Candle, ...]]],
    ) -> BacktestResult:
        ledgers = {
            kind: Ledger(config.initial_capital * self._strategy_weight(config, kind))
            for kind in StrategyKind
        }
        execution = ExecutionModel(config.fee_rate, config.slippage_bps)

        for kind in StrategyKind:
            expected_symbols = {
                item.symbol: item.weight
                for item in config.universes[kind.value].symbols
            }
            supplied = datasets.get(kind, {})
            if set(supplied) != set(expected_symbols):
                raise ValueError(f"datasets for {kind.value} do not match configured symbols")
            for symbol in sorted(supplied):
                series = supplied[symbol]
                if len(series) < 2:
                    raise ValueError("each backtest dataset requires at least two candles")
                strategy = self.strategy_factory[kind](config, symbol)
                self._run_symbol(
                    strategy=strategy,
                    symbol=symbol,
                    symbol_weight=expected_symbols[symbol],
                    series=series,
                    ledger=ledgers[kind],
                    execution=execution,
                )

        return BacktestResult(
            ledgers=ledgers,
            cash_reserve=config.initial_capital * config.allocations.cash_reserve,
            fingerprint=self._fingerprint(config, datasets),
            engine_version=self.VERSION,
            final_prices={
                kind: {symbol: series[-1].close for symbol, series in supplied.items()}
                for kind, supplied in datasets.items()
            },
        )

    def _run_symbol(
        self,
        strategy: Strategy,
        symbol: str,
        symbol_weight: Decimal,
        series: tuple[Candle, ...],
        ledger: Ledger,
        execution: ExecutionModel,
    ) -> None:
        state = StrategyState(values={"symbol": symbol})
        for index in range(len(series) - 1):
            state = self._before_decision(state, ledger, symbol, series[index].close)
            intents = strategy.generate(index, CandleWindow(series, index), state)
            for intent in intents:
                sized = intent
                if intent.side is Side.BUY and intent.allocation is not None:
                    sized = intent.model_copy(
                        update={"allocation": intent.allocation * symbol_weight}
                    )
                fill = execution.fill(sized, series[index + 1], ledger)
                if fill is None:
                    continue
                ledger.apply(fill)
                state = self._after_fill(state, ledger, symbol, index, fill)

    @staticmethod
    def _before_decision(
        state: StrategyState,
        ledger: Ledger,
        symbol: str,
        close: Decimal,
    ) -> StrategyState:
        values = dict(state.values)
        position = ledger.position(symbol)
        positions = {symbol: position} if position.quantity else {}
        if position.quantity:
            values["holding_candles"] = int(values.get("holding_candles", 0)) + 1
            values["peak_price"] = max(
                Decimal(values.get("peak_price", close)), close
            )
        return StrategyState(positions=positions, values=values)

    @staticmethod
    def _after_fill(
        state: StrategyState,
        ledger: Ledger,
        symbol: str,
        index: int,
        fill: Fill,
    ) -> StrategyState:
        values = dict(state.values)
        position = ledger.position(symbol)
        if fill.side is Side.BUY:
            values["entry_count"] = int(values.get("entry_count", 0)) + 1
            values["last_entry_price"] = fill.price
            values["peak_price"] = max(
                Decimal(values.get("peak_price", fill.price)), fill.price
            )
            values["holding_candles"] = 0
        elif not position.quantity:
            values.update(
                entry_count=0,
                last_exit_index=index,
                holding_candles=0,
            )
            values.pop("peak_price", None)
        positions = {symbol: position} if position.quantity else {}
        return StrategyState(positions=positions, values=values)

    @staticmethod
    def _strategy_weight(config: BacktestConfig, kind: StrategyKind) -> Decimal:
        return {
            StrategyKind.TREND: config.allocations.trend,
            StrategyKind.MEAN_REVERSION: config.allocations.mean_reversion,
            StrategyKind.GRID: config.allocations.grid,
        }[kind]

    def _fingerprint(
        self,
        config: BacktestConfig,
        datasets: dict[StrategyKind, dict[str, tuple[Candle, ...]]],
    ) -> str:
        payload = {
            "engine_version": self.VERSION,
            "config": config.model_dump(mode="json"),
            "datasets": {
                kind.value: {
                    symbol: [candle.model_dump(mode="json") for candle in candles]
                    for symbol, candles in sorted(by_symbol.items())
                }
                for kind, by_symbol in sorted(datasets.items(), key=lambda item: item[0].value)
            },
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
