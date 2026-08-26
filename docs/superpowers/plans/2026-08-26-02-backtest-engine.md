# Multi-Strategy Backtest Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver deterministic backtests for trend, mean-reversion, and grid strategies with independent ledgers, shared portfolio limits, immutable run snapshots, metrics, and CSV export.

**Architecture:** Pure domain modules implement signals, risk, fills, ledgers, and metrics without network or database access. An application service loads fingerprinted candle datasets, executes one ledger per strategy, aggregates results, and persists immutable snapshots.

**Tech Stack:** Python 3.12, Pydantic 2, SQLAlchemy 2, NumPy, pytest, Hypothesis

**Spec:** `docs/superpowers/specs/2026-08-26-binance-multi-strategy-backtest-design.md`

## Global Constraints

- Signals use closed candles only; standard fills occur at the next candle open.
- Decimal is used for cash, quantity, price, fee, and profit/loss accounting.
- Strategy ledgers remain independent even when signals conflict on the same symbol.
- No ledger may have negative cash or sell more inventory than it owns.
- Identical dataset, engine version, and parameters must produce identical results.

---

### Task 1: Backtest Contracts and Validated Run Configuration

**Files:**
- Create: `src/quant_home/backtest/types.py`
- Create: `src/quant_home/backtest/config.py`
- Create: `src/quant_home/strategies/base.py`
- Test: `tests/backtest/test_config.py`

**Interfaces:**
- Produces: `StrategySignal`, `OrderIntent`, `Fill`, `Position`, `EquityPoint`
- Produces: `BacktestConfig.model_validate(data) -> BacktestConfig`
- Produces: `Strategy.generate(index: int, candles: CandleWindow, state: StrategyState) -> list[OrderIntent]`

- [ ] **Step 1: Write failing allocation and timeframe validation tests**

```python
def test_strategy_allocations_and_reserve_must_total_one():
    with pytest.raises(ValidationError):
        BacktestConfig.model_validate({
            "trend_weight": "0.40", "mean_weight": "0.30",
            "grid_weight": "0.20", "cash_reserve": "0.20",
        })

def test_fast_period_must_be_less_than_slow_period():
    with pytest.raises(ValidationError):
        TrendConfig(fast_period=50, slow_period=20)
```

- [ ] **Step 2: Verify configuration tests fail**

Run: `docker compose run --rm api pytest tests/backtest/test_config.py -v`

Expected: FAIL because contracts are absent.

- [ ] **Step 3: Implement frozen DTOs and server-side validators**

```python
class AllocationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    trend: Decimal
    mean_reversion: Decimal
    grid: Decimal
    cash_reserve: Decimal

    @model_validator(mode="after")
    def total_is_one(self):
        if sum((self.trend, self.mean_reversion, self.grid, self.cash_reserve)) != Decimal("1"):
            raise ValueError("strategy allocations and cash reserve must total 1")
        return self
```

- [ ] **Step 4: Run configuration tests**

Run: `docker compose run --rm api pytest tests/backtest/test_config.py -v`

Expected: PASS for valid defaults and all documented invalid boundaries.

- [ ] **Step 5: Commit contracts**

```bash
git add src/quant_home/backtest src/quant_home/strategies/base.py tests/backtest/test_config.py
git commit -m "feat: define backtest contracts"
```

### Task 2: Ledger and Conservative Execution Model

**Files:**
- Create: `src/quant_home/backtest/ledger.py`
- Create: `src/quant_home/backtest/execution.py`
- Test: `tests/backtest/test_ledger.py`
- Test: `tests/backtest/test_execution.py`

**Interfaces:**
- Produces: `Ledger.apply(fill: Fill) -> None`
- Produces: `ExecutionModel.fill(intent: OrderIntent, next_candle: Candle, ledger: Ledger) -> Fill | None`

- [ ] **Step 1: Write failing conservation and ambiguous-candle tests**

```python
def test_round_trip_conserves_cash_after_fee():
    ledger = Ledger(initial_cash=Decimal("1000"))
    ledger.apply(Fill.buy("BTCUSDT", Decimal("1"), Decimal("100"), Decimal("0.10")))
    ledger.apply(Fill.sell("BTCUSDT", Decimal("1"), Decimal("110"), Decimal("0.11")))
    assert ledger.cash == Decimal("1009.79")
    assert ledger.position_quantity("BTCUSDT") == 0

def test_stop_and_target_same_candle_uses_stop_first(conservative_model):
    fill = conservative_model.resolve_exit(stop=Decimal("95"), target=Decimal("110"), candle=candle(low="94", high="111"))
    assert fill.price == Decimal("95")
```

- [ ] **Step 2: Verify ledger tests fail**

Run: `docker compose run --rm api pytest tests/backtest/test_ledger.py tests/backtest/test_execution.py -v`

Expected: FAIL because accounting and execution are absent.

- [ ] **Step 3: Implement next-open, crossed-limit, slippage, fee, and inventory rules**

```python
def market_fill_price(side: Side, next_open: Decimal, slippage_bps: Decimal) -> Decimal:
    direction = Decimal("1") if side is Side.BUY else Decimal("-1")
    return next_open * (Decimal("1") + direction * slippage_bps / Decimal("10000"))
```

Reject fills that require unavailable cash or inventory. Quantize only at exchange-rule boundaries, not during internal profit/loss calculations.

- [ ] **Step 4: Add property tests and run them**

Run: `docker compose run --rm api pytest tests/backtest/test_ledger.py tests/backtest/test_execution.py -v`

Expected: PASS; Hypothesis never produces negative cash or inventory.

- [ ] **Step 5: Commit accounting and execution**

```bash
git add src/quant_home/backtest/ledger.py src/quant_home/backtest/execution.py tests/backtest
git commit -m "feat: add conservative execution ledger"
```

### Task 3: Shared Portfolio Risk

**Files:**
- Create: `src/quant_home/backtest/risk.py`
- Test: `tests/backtest/test_risk.py`

**Interfaces:**
- Produces: `RiskManager.evaluate(intent: OrderIntent, context: RiskContext) -> RiskDecision`
- Produces: `RiskDecision(allowed: bool, adjusted_quantity: Decimal, reason: str | None)`

- [ ] **Step 1: Write failing exposure and drawdown tests**

```python
def test_entry_is_rejected_after_drawdown_stop(risk_manager):
    decision = risk_manager.evaluate(buy_intent(), context(drawdown=Decimal("0.21"), max_drawdown=Decimal("0.20")))
    assert decision.allowed is False
    assert decision.reason == "MAX_DRAWDOWN"

def test_exit_is_allowed_when_entries_are_stopped(risk_manager):
    assert risk_manager.evaluate(sell_existing_position(), stopped_context()).allowed
```

- [ ] **Step 2: Verify risk tests fail**

Run: `docker compose run --rm api pytest tests/backtest/test_risk.py -v`

Expected: FAIL because risk decisions are absent.

- [ ] **Step 3: Implement per-symbol, per-strategy, total exposure, loss, and drawdown limits**

```python
class RiskReason(StrEnum):
    SYMBOL_EXPOSURE = "SYMBOL_EXPOSURE"
    STRATEGY_EXPOSURE = "STRATEGY_EXPOSURE"
    TOTAL_EXPOSURE = "TOTAL_EXPOSURE"
    DAILY_LOSS = "DAILY_LOSS"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
```

- [ ] **Step 4: Run focused and property tests**

Run: `docker compose run --rm api pytest tests/backtest/test_risk.py -v`

Expected: PASS; rejected entries never mutate ledgers.

- [ ] **Step 5: Commit risk controls**

```bash
git add src/quant_home/backtest/risk.py tests/backtest/test_risk.py
git commit -m "feat: enforce portfolio risk limits"
```

### Task 4: Trend-Following Strategy

**Files:**
- Create: `src/quant_home/strategies/trend.py`
- Test: `tests/strategies/test_trend.py`

**Interfaces:**
- Produces: `TrendStrategy(config: TrendConfig)` implementing `Strategy`

- [ ] **Step 1: Write a fixed-candle golden signal test**

```python
def test_trend_enters_after_confirmed_cross_and_exits_on_stop():
    signals = run_strategy(TrendStrategy(TrendConfig(fast_period=2, slow_period=3)), trend_fixture())
    assert [(s.index, s.side, s.reason) for s in signals] == [
        (4, Side.BUY, "FAST_ABOVE_SLOW"),
        (7, Side.SELL, "FIXED_STOP"),
    ]
```

- [ ] **Step 2: Verify the golden test fails**

Run: `docker compose run --rm api pytest tests/strategies/test_trend.py -v`

Expected: FAIL because the strategy is absent.

- [ ] **Step 3: Implement EMA/SMA crossover, confirmation, cooldown, fixed and trailing stops**

```python
if crossed_above(fast, slow, index) and confirmed_for(config.confirmation_candles):
    return [OrderIntent.market_buy(reason="FAST_ABOVE_SLOW", allocation=config.entry_allocation)]
```

- [ ] **Step 4: Run trend tests including no-lookahead mutation test**

Run: `docker compose run --rm api pytest tests/strategies/test_trend.py -v`

Expected: PASS when future candles are changed without changing earlier signals.

- [ ] **Step 5: Commit trend strategy**

```bash
git add src/quant_home/strategies/trend.py tests/strategies/test_trend.py
git commit -m "feat: add trend strategy"
```

### Task 5: Mean-Reversion Strategy

**Files:**
- Create: `src/quant_home/strategies/mean_reversion.py`
- Test: `tests/strategies/test_mean_reversion.py`

**Interfaces:**
- Produces: `MeanReversionStrategy(config: MeanReversionConfig)` implementing `Strategy`

- [ ] **Step 1: Write fixed RSI/Bollinger entry, staged-entry, timeout, and stop tests**

```python
def test_mean_reversion_requires_rsi_and_lower_band():
    signals = run_strategy(strategy(), oversold_fixture())
    assert signals[0].reason == "RSI_AND_LOWER_BAND"
    assert signals[0].stage == 1
```

- [ ] **Step 2: Verify mean-reversion tests fail**

Run: `docker compose run --rm api pytest tests/strategies/test_mean_reversion.py -v`

Expected: FAIL because the strategy is absent.

- [ ] **Step 3: Implement RSI, Bollinger bands, bounded staged entries, exit threshold, timeout, stop, and target**

```python
entry_ready = rsi[index] < config.rsi_entry and close[index] <= lower_band[index]
exit_ready = rsi[index] > config.rsi_exit or state.holding_candles >= config.max_holding_candles
```

- [ ] **Step 4: Run mean-reversion tests and no-lookahead test**

Run: `docker compose run --rm api pytest tests/strategies/test_mean_reversion.py -v`

Expected: PASS; staged entries never exceed the configured count.

- [ ] **Step 5: Commit mean-reversion strategy**

```bash
git add src/quant_home/strategies/mean_reversion.py tests/strategies/test_mean_reversion.py
git commit -m "feat: add mean reversion strategy"
```

### Task 6: Grid Strategy

**Files:**
- Create: `src/quant_home/strategies/grid.py`
- Test: `tests/strategies/test_grid.py`

**Interfaces:**
- Produces: `GridStrategy(config: GridConfig)` implementing `Strategy`
- Produces: `build_grid(config: GridConfig) -> tuple[Decimal, ...]`

- [ ] **Step 1: Write arithmetic, geometric, crossing-order, inventory, and out-of-range tests**

```python
def test_grid_fills_crossed_levels_in_price_path_order():
    signals = run_grid(candle(open="100", low="90", high="105", close="95"), levels=(90, 95, 100, 105))
    assert [signal.level for signal in signals] == [95, 90, 95, 100, 105, 100, 95]
```

Use a deterministic conservative path assumption documented in the test fixture; do not infer true intrabar order.

- [ ] **Step 2: Verify grid tests fail**

Run: `docker compose run --rm api pytest tests/strategies/test_grid.py -v`

Expected: FAIL because grid construction and state are absent.

- [ ] **Step 3: Implement grids, bounded inventory, stop behavior, and optional re-grid cooldown**

```python
def arithmetic_levels(lower: Decimal, upper: Decimal, count: int) -> tuple[Decimal, ...]:
    step = (upper - lower) / Decimal(count)
    return tuple(lower + step * index for index in range(count + 1))
```

- [ ] **Step 4: Run grid tests**

Run: `docker compose run --rm api pytest tests/strategies/test_grid.py -v`

Expected: PASS; default out-of-range behavior stops new entries and does not auto-close.

- [ ] **Step 5: Commit grid strategy**

```bash
git add src/quant_home/strategies/grid.py tests/strategies/test_grid.py
git commit -m "feat: add grid strategy"
```

### Task 7: Multi-Strategy Engine and Immutable Persistence

**Files:**
- Create: `src/quant_home/backtest/engine.py`
- Create: `src/quant_home/backtest/models.py`
- Create: `src/quant_home/backtest/repository.py`
- Create: `src/quant_home/backtest/service.py`
- Create: `alembic/versions/0004_backtests.py`
- Test: `tests/backtest/test_engine.py`
- Test: `tests/backtest/test_repository.py`

**Interfaces:**
- Produces: `BacktestEngine.run(config, datasets) -> BacktestResult`
- Produces: `BacktestService.create_run(request: CreateBacktestRequest) -> UUID`
- Produces: `BacktestRepository.save_completed(result: BacktestResult) -> UUID`

- [ ] **Step 1: Write failing independent-ledger and deterministic-result tests**

```python
def test_opposite_signals_do_not_net_strategy_ledgers(engine):
    result = engine.run(config(), datasets())
    assert result.ledgers[StrategyKind.TREND].position("BTCUSDT") != result.ledgers[StrategyKind.MEAN].position("BTCUSDT")

def test_same_inputs_have_same_result_fingerprint(engine):
    assert engine.run(config(), datasets()).fingerprint == engine.run(config(), datasets()).fingerprint
```

- [ ] **Step 2: Verify engine tests fail**

Run: `docker compose run --rm api pytest tests/backtest/test_engine.py -v`

Expected: FAIL because orchestration is absent.

- [ ] **Step 3: Implement chronological execution, one ledger per strategy, shared risk context, and atomic persistence**

```python
for index in range(len(timeline)):
    for strategy_kind in StrategyKind:
        intents = strategies[strategy_kind].generate(index, windows[strategy_kind], states[strategy_kind])
        execute_allowed_intents(intents, ledgers[strategy_kind], shared_risk)
```

- [ ] **Step 4: Run engine and repository tests**

Run: `docker compose run --rm api pytest tests/backtest/test_engine.py tests/backtest/test_repository.py -v`

Expected: PASS; completed runs are immutable and failed transactions expose no completed result.

- [ ] **Step 5: Commit engine and persistence**

```bash
git add src/quant_home/backtest alembic/versions/0004_backtests.py tests/backtest
git commit -m "feat: run independent strategy backtests"
```

### Task 8: Metrics, Benchmark, API, and CSV Export

**Files:**
- Create: `src/quant_home/backtest/metrics.py`
- Create: `src/quant_home/backtest/export.py`
- Create: `src/quant_home/api/backtests.py`
- Test: `tests/backtest/test_metrics.py`
- Test: `tests/api/test_backtests_api.py`

**Interfaces:**
- Produces: `calculate_metrics(equity, fills, periods_per_year) -> PerformanceSummary`
- Produces: `build_trade_csv(run_id: UUID) -> Iterator[str]`
- Produces: authenticated create, list, detail, cancel, and export endpoints

- [ ] **Step 1: Write failing known-series metric and CSV tests**

```python
def test_max_drawdown_for_known_equity_series():
    summary = calculate_metrics([100, 120, 90, 110], [], periods_per_year=365)
    assert summary.max_drawdown == Decimal("0.25")

def test_trade_csv_contains_strategy_and_dataset_fingerprint(client, completed_run):
    text = client.get(f"/api/backtests/{completed_run.id}/trades.csv").text
    assert "strategy,symbol,side,quantity,price,fee" in text
```

- [ ] **Step 2: Verify metrics and API tests fail**

Run: `docker compose run --rm api pytest tests/backtest/test_metrics.py tests/api/test_backtests_api.py -v`

Expected: FAIL because reporting is absent.

- [ ] **Step 3: Implement returns, annualization, drawdown, win rate, profit factor, Sharpe, fees, exposure, attribution, and buy-and-hold**

```python
drawdowns = [(peak - value) / peak for peak, value in running_peak_pairs(equity)]
max_drawdown = max(drawdowns, default=Decimal("0"))
```

- [ ] **Step 4: Run the full backtest suite**

Run: `docker compose run --rm api pytest tests/backtest tests/strategies tests/api/test_backtests_api.py -q`

Expected: PASS, including fixed-dataset regression snapshots.

- [ ] **Step 5: Commit reporting**

```bash
git add src/quant_home/backtest/metrics.py src/quant_home/backtest/export.py src/quant_home/api/backtests.py tests/backtest tests/api/test_backtests_api.py
git commit -m "feat: report and export backtest results"
```

### Task 9: Named Strategy Configuration API

**Files:**
- Create: `src/quant_home/configurations/models.py`
- Create: `src/quant_home/configurations/repository.py`
- Create: `src/quant_home/configurations/service.py`
- Create: `src/quant_home/api/configurations.py`
- Create: `alembic/versions/0005_strategy_configurations.py`
- Test: `tests/api/test_configurations_api.py`

**Interfaces:**
- Produces: authenticated create, list, clone, update, delete, import, export, and defaults endpoints
- Produces: immutable `configuration_version` snapshots referenced by backtest runs

- [ ] **Step 1: Write failing clone, defaults, and immutable-snapshot tests**

```python
def test_editing_named_configuration_does_not_change_completed_run(client, completed_run):
    original = completed_run.configuration_snapshot
    client.put(f"/api/configurations/{completed_run.configuration_id}", json=changed_configuration(), headers=csrf_headers())
    assert get_run(completed_run.id).configuration_snapshot == original
```

- [ ] **Step 2: Verify configuration API tests fail**

Run: `docker compose run --rm api pytest tests/api/test_configurations_api.py -v`

Expected: FAIL because named configuration persistence is absent.

- [ ] **Step 3: Implement versioned named configurations and validated JSON import/export**

```python
class StrategyConfiguration(Base):
    __tablename__ = "strategy_configurations"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    version: Mapped[int]
    payload: Mapped[dict] = mapped_column(JSON)
```

Every update creates a new version. Backtest runs copy the validated payload and reference its version.

- [ ] **Step 4: Run configuration and backtest snapshot tests**

Run: `docker compose run --rm api pytest tests/api/test_configurations_api.py tests/backtest/test_repository.py -v`

Expected: PASS; malformed imports return validation details and do not write a partial configuration.

- [ ] **Step 5: Commit named configurations**

```bash
git add src/quant_home/configurations src/quant_home/api/configurations.py alembic/versions/0005_strategy_configurations.py tests/api/test_configurations_api.py
git commit -m "feat: version strategy configurations"
```
