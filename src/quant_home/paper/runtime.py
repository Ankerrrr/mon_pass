from copy import deepcopy
from decimal import Decimal
from typing import Any
from uuid import UUID

from quant_home.backtest.config import BacktestConfig
from quant_home.backtest.engine import BacktestEngine
from quant_home.backtest.execution import ExecutionModel
from quant_home.backtest.ledger import Ledger
from quant_home.backtest.types import Fill, StrategyKind, TradingMode
from quant_home.market.candles import Candle
from quant_home.market.stream import CandleClosed
from quant_home.paper.repository import PaperRepository
from quant_home.strategies.base import CandleWindow, StrategyState


class PaperRuntime:
    """Processes closed candles with the same strategies and fill model as backtests."""

    def __init__(self, session_id: UUID, repository: PaperRepository) -> None:
        self.session_id = session_id
        self.repository = repository

    def on_candle(self, event: CandleClosed) -> int:
        session = self.repository.get(self.session_id)
        config = BacktestConfig.model_validate(session.configuration_snapshot)
        state = deepcopy(session.state_snapshot)
        processed = 0
        for kind in StrategyKind:
            universe = config.universes[kind.value]
            if universe.interval != event.interval or event.symbol not in {item.symbol for item in universe.symbols}:
                continue
            if self.repository.was_processed(self.session_id, kind.value, event):
                continue
            self._process_strategy(state, config, kind, event)
            if self.repository.checkpoint(
                self.session_id, state, strategy=kind.value, symbol=event.symbol,
                interval=event.interval.value, open_time=event.candle.open_time,
            ):
                processed += 1
        return processed

    @staticmethod
    def _process_strategy(state: dict[str, Any], config: BacktestConfig, kind: StrategyKind, event: CandleClosed) -> None:
        key = f"{kind.value}:{event.symbol}"
        candle_rows = state.setdefault("candles", {}).setdefault(key, [])
        candle_rows.append(event.candle.model_dump(mode="json"))
        candle_rows[:] = candle_rows[-1002:]
        state.setdefault("last_prices", {}).setdefault(kind.value, {})[event.symbol] = str(event.candle.close)
        if len(candle_rows) < 2:
            return
        candles = tuple(Candle.model_validate(row) for row in candle_rows)
        ledger_row = state["ledgers"][kind.value]
        ledger = Ledger(Decimal(ledger_row["initial_cash"]))
        for fill_row in ledger_row["fills"]:
            ledger.apply(Fill.model_validate(fill_row))
        stored_state = state.setdefault("strategy_states", {}).get(key, {"values": {"symbol": event.symbol}})
        strategy_state = StrategyState(
            positions={name: ledger.position(name) for name in ledger_row.get("positions", {})},
            values=stored_state.get("values", {"symbol": event.symbol}),
        )
        decision_index = len(candles) - 2
        strategy_state = BacktestEngine._before_decision(
            strategy_state, ledger, event.symbol, candles[decision_index].close
        )
        factory = BacktestEngine().strategy_factory[kind]
        strategy = factory(config, event.symbol)
        execution = ExecutionModel(config.fee_rate, config.slippage_bps)
        weight = next(item.weight for item in config.universes[kind.value].symbols if item.symbol == event.symbol)
        for intent in strategy.generate(decision_index, CandleWindow(candles, decision_index), strategy_state):
            if intent.allocation is not None and intent.side.value == "buy":
                intent = intent.model_copy(update={"allocation": intent.allocation * weight})
            fill = execution.fill(intent, event.candle, ledger)
            if fill is None:
                continue
            fill = fill.model_copy(update={"mode": TradingMode.PAPER})
            ledger.apply(fill)
            strategy_state = BacktestEngine._after_fill(strategy_state, ledger, event.symbol, decision_index, fill)
        positions = {}
        for symbol in {item.symbol for item in config.universes[kind.value].symbols}:
            position = ledger.position(symbol)
            if position.quantity:
                positions[symbol] = position.model_dump(mode="json")
        state["ledgers"][kind.value] = {
            "initial_cash": str(ledger.initial_cash), "cash": str(ledger.cash),
            "positions": positions, "fills": [fill.model_dump(mode="json") for fill in ledger.fills],
        }
        state["strategy_states"][key] = {"values": PaperRuntime._json_values(strategy_state.values)}

    @staticmethod
    def _json_values(values: dict[str, Any]) -> dict[str, Any]:
        return {key: str(value) if isinstance(value, Decimal) else value for key, value in values.items()}
