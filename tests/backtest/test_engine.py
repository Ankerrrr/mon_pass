from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant_home.backtest.config import BacktestConfig
from quant_home.backtest.engine import BacktestEngine
from quant_home.backtest.types import OrderIntent, OrderType, Side, StrategyKind
from quant_home.market.candles import Candle


def candles() -> tuple[Candle, ...]:
    result = []
    for index, price in enumerate(("100", "110", "120")):
        opened = datetime(2025, 1, 1, tzinfo=UTC) + timedelta(hours=index)
        value = Decimal(price)
        result.append(
            Candle(
                open_time=opened,
                open=value,
                high=value,
                low=value,
                close=value,
                volume=Decimal("1"),
                close_time=opened + timedelta(hours=1),
            )
        )
    return tuple(result)


def config() -> BacktestConfig:
    return BacktestConfig(
        initial_capital=Decimal("1000"),
        start_time=datetime(2025, 1, 1, tzinfo=UTC),
        end_time=datetime(2025, 1, 2, tzinfo=UTC),
        allocations={
            "trend": "0.4",
            "mean_reversion": "0.3",
            "grid": "0.2",
            "cash_reserve": "0.1",
        },
        universes={
            name: {"symbols": [{"symbol": "BTCUSDT", "weight": "1"}]}
            for name in ("trend", "mean_reversion", "grid")
        },
    )


class BuyAndHold:
    def generate(self, index, candles, state):
        if index == 0 and not state.positions:
            return [OrderIntent.market_buy("BTCUSDT", "BUY", Decimal("1"))]
        return []


class RoundTrip:
    def generate(self, index, candles, state):
        if index == 0 and not state.positions:
            return [OrderIntent.market_buy("BTCUSDT", "BUY", Decimal("1"))]
        position = state.positions.get("BTCUSDT")
        if index == 1 and position and position.quantity:
            return [
                OrderIntent(
                    symbol="BTCUSDT",
                    side=Side.SELL,
                    order_type=OrderType.MARKET,
                    reason="SELL",
                    quantity=position.quantity,
                )
            ]
        return []


class NoSignals:
    def generate(self, index, candles, state):
        return []


def test_engine_keeps_strategy_ledgers_independent_and_uses_next_open():
    engine = BacktestEngine(
        strategy_factory={
            StrategyKind.TREND: lambda *_: BuyAndHold(),
            StrategyKind.MEAN_REVERSION: lambda *_: RoundTrip(),
            StrategyKind.GRID: lambda *_: NoSignals(),
        }
    )
    datasets = {
        kind: {"BTCUSDT": candles()}
        for kind in StrategyKind
    }

    result = engine.run(config(), datasets)

    trend = result.ledgers[StrategyKind.TREND]
    mean = result.ledgers[StrategyKind.MEAN_REVERSION]
    assert trend.fills[0].price == Decimal("110.0550")
    assert trend.position_quantity("BTCUSDT") > 0
    assert mean.position_quantity("BTCUSDT") == 0
    assert len(mean.fills) == 2


def test_same_inputs_have_same_result_fingerprint():
    engine = BacktestEngine(
        strategy_factory={kind: lambda *_: NoSignals() for kind in StrategyKind}
    )
    datasets = {kind: {"BTCUSDT": candles()} for kind in StrategyKind}

    first = engine.run(config(), datasets)
    second = engine.run(config(), datasets)

    assert first.fingerprint == second.fingerprint
    assert first.fingerprint
