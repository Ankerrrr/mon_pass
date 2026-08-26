# Paper Trading and Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver restart-safe real-time paper trading on public Binance data, operational monitoring, local backup/restore, and final LAN acceptance without real order capability.

**Architecture:** A market-stream adapter emits normalized closed-candle events into the existing strategy, risk, execution, and ledger interfaces. Paper sessions checkpoint immutable configuration and mutable ledgers to PostgreSQL; a supervisor owns reconnect, data-gap reconciliation, stop controls, and health reporting.

**Tech Stack:** Python 3.12, FastAPI, asyncio, HTTPX/WebSocket client, SQLAlchemy 2, PostgreSQL 16, React 19, pytest, Playwright, Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-26-binance-multi-strategy-backtest-design.md`

## Global Constraints

- Paper trading uses public Binance market data and cannot place or sign a real order.
- Paper trading reuses the tested backtest strategy, risk, execution, and ledger interfaces.
- Only closed candles generate decisions.
- Restart recovery reconciles missing candles before emitting new signals.
- Simulation mode and stop controls remain visible on every paper-trading screen.

---

### Task 1: Normalized Public Market Stream

**Files:**
- Create: `src/quant_home/market/stream.py`
- Create: `src/quant_home/market/reconnect.py`
- Test: `tests/market/test_stream.py`
- Test: `tests/market/test_reconnect.py`

**Interfaces:**
- Produces: `MarketStream.subscribe(subscriptions: set[StreamSubscription]) -> AsyncIterator[CandleClosed]`
- Produces: `ReconnectPolicy.next_delay(attempt: int) -> float`
- Consumes: `CandleRepository.ensure_range(...)` for gap repair

- [ ] **Step 1: Write failing closed-candle, disconnect, and gap tests**

```python
async def test_stream_emits_only_closed_candles(stream, websocket):
    websocket.feed(kline_event(closed=False))
    websocket.feed(kline_event(closed=True, open_time="2026-01-01T00:00:00Z"))
    event = await anext(stream)
    assert event.candle.open_time == datetime(2026, 1, 1, tzinfo=UTC)

async def test_reconnect_repairs_gap_before_new_event(supervisor):
    await supervisor.disconnect_after(last_open_time="2026-01-01T00:00:00Z")
    await supervisor.reconnect_with(first_open_time="2026-01-01T03:00:00Z")
    assert supervisor.calls[0].name == "ensure_range"
```

- [ ] **Step 2: Verify stream tests fail**

Run: `docker compose run --rm api pytest tests/market/test_stream.py tests/market/test_reconnect.py -v`

Expected: FAIL because the stream adapter is absent.

- [ ] **Step 3: Implement normalized subscriptions, ping/pong handling, bounded exponential reconnect, resubscription, and gap repair**

```python
@dataclass(frozen=True)
class CandleClosed:
    symbol: str
    interval: CandleInterval
    candle: Candle

def next_delay(attempt: int) -> float:
    return min(30.0, 0.5 * (2 ** attempt))
```

- [ ] **Step 4: Run stream and reconnect tests**

Run: `docker compose run --rm api pytest tests/market/test_stream.py tests/market/test_reconnect.py -v`

Expected: PASS; duplicate closed candles are ignored by `(symbol, interval, open_time)` identity.

- [ ] **Step 5: Commit stream adapter**

```bash
git add src/quant_home/market/stream.py src/quant_home/market/reconnect.py tests/market
git commit -m "feat: stream public closed candles"
```

### Task 2: Restart-Safe Paper Session Runtime

**Files:**
- Create: `src/quant_home/paper/types.py`
- Create: `src/quant_home/paper/models.py`
- Create: `src/quant_home/paper/repository.py`
- Create: `src/quant_home/paper/runtime.py`
- Create: `src/quant_home/paper/service.py`
- Create: `alembic/versions/0006_paper_sessions.py`
- Test: `tests/paper/test_runtime.py`
- Test: `tests/paper/test_recovery.py`

**Interfaces:**
- Produces: `PaperTradingService.start(config_id: UUID) -> UUID`
- Produces: `PaperTradingService.stop(session_id: UUID) -> None`
- Produces: `PaperRuntime.on_candle(event: CandleClosed) -> None`
- Produces: `PaperRepository.checkpoint(session: PaperSessionState) -> None`

- [ ] **Step 1: Write failing engine-reuse and recovery tests**

```python
async def test_closed_candle_uses_same_strategy_and_execution_interfaces(runtime, fake_strategy):
    await runtime.on_candle(closed_candle())
    fake_strategy.generate.assert_called_once()
    assert runtime.ledger.fills[0].mode is TradingMode.PAPER

def test_recovery_restores_each_strategy_ledger(repository, saved_session):
    restored = repository.load_state(saved_session.id)
    assert restored.ledgers[StrategyKind.GRID].cash == Decimal("2000")
```

- [ ] **Step 2: Verify paper runtime tests fail**

Run: `docker compose run --rm api pytest tests/paper/test_runtime.py tests/paper/test_recovery.py -v`

Expected: FAIL because paper sessions are absent.

- [ ] **Step 3: Implement immutable config snapshots, independent ledgers, idempotent candle handling, checkpoints, start, and stop**

```python
async def on_candle(self, event: CandleClosed) -> None:
    if self.repository.was_processed(self.session_id, event):
        return
    self.engine.process_closed_candle(self.state, event)
    self.repository.checkpoint_and_mark_processed(self.state, event)
```

- [ ] **Step 4: Run runtime and crash-recovery tests**

Run: `docker compose run --rm api pytest tests/paper -v`

Expected: PASS; replaying the last candle after restart creates no duplicate fill.

- [ ] **Step 5: Commit paper runtime**

```bash
git add src/quant_home/paper alembic/versions/0006_paper_sessions.py tests/paper
git commit -m "feat: add restart-safe paper trading"
```

### Task 3: Paper Trading API, Audit, and Emergency Stop

**Files:**
- Create: `src/quant_home/audit/models.py`
- Create: `src/quant_home/audit/service.py`
- Create: `src/quant_home/api/paper.py`
- Modify: `src/quant_home/api/configurations.py`
- Modify: `src/quant_home/api/backtests.py`
- Create: `alembic/versions/0007_audit_events.py`
- Test: `tests/api/test_paper_api.py`
- Test: `tests/audit/test_audit.py`

**Interfaces:**
- Produces: authenticated list, detail, start, stop, and emergency-stop endpoints
- Produces: `AuditService.record(actor_id, action, subject_type, subject_id, metadata) -> None`
- Produces: audit records for configuration changes, backtest deletion, and every paper-session control

- [ ] **Step 1: Write failing authorization, idempotent stop, and audit tests**

```python
def test_emergency_stop_stops_all_sessions_and_records_actor(client, active_sessions, admin):
    response = client.post("/api/paper/emergency-stop", headers=csrf_headers())
    assert response.status_code == 200
    assert response.json()["stopped"] == len(active_sessions)
    assert latest_audit().actor_id == admin.id
    assert latest_audit().action == "PAPER_EMERGENCY_STOP"
```

- [ ] **Step 2: Verify paper API tests fail**

Run: `docker compose run --rm api pytest tests/api/test_paper_api.py tests/audit/test_audit.py -v`

Expected: FAIL because endpoints and audit records are absent.

- [ ] **Step 3: Implement CSRF-protected controls, idempotent stop semantics, and structured audit metadata across sensitive endpoints**

```python
@router.post("/paper/emergency-stop")
def emergency_stop(admin=Depends(require_admin), service=Depends(paper_service)):
    stopped = service.stop_all(reason="administrator emergency stop")
    return {"stopped": stopped}
```

- [ ] **Step 4: Run API and audit tests**

Run: `docker compose run --rm api pytest tests/api/test_paper_api.py tests/audit/test_audit.py -v`

Expected: PASS; repeated stop requests do not create duplicate exits or fills.

- [ ] **Step 5: Commit controls and audit**

```bash
git add src/quant_home/audit src/quant_home/api/paper.py src/quant_home/api/configurations.py src/quant_home/api/backtests.py alembic/versions/0007_audit_events.py tests/api/test_paper_api.py tests/audit
git commit -m "feat: control and audit paper sessions"
```

### Task 4: Paper Dashboard and Operational Health

**Files:**
- Create: `frontend/src/paper/PaperTradingPage.tsx`
- Create: `frontend/src/paper/PaperSessionPage.tsx`
- Create: `frontend/src/paper/EmergencyStopButton.tsx`
- Create: `src/quant_home/api/system.py`
- Test: `frontend/src/paper/PaperTradingPage.test.tsx`
- Test: `tests/api/test_system_health.py`

**Interfaces:**
- Consumes: paper session APIs and `/system/health`
- Produces: stream status, last candle, strategy ledgers, exposure, drawdown, fills, warnings, start/stop controls

- [ ] **Step 1: Write failing disconnected-stream and emergency-stop UI tests**

```tsx
it("keeps simulation status visible and confirms emergency stop", async () => {
  render(<PaperTradingPage />);
  expect(screen.getByText("模擬模式｜不會送出真實訂單")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "緊急停止全部模擬" }));
  expect(screen.getByRole("dialog", { name: "確認緊急停止" })).toBeVisible();
});
```

- [ ] **Step 2: Verify dashboard tests fail**

Run: `docker compose run --rm web npm test -- PaperTradingPage.test.tsx`

Expected: FAIL because paper views are absent.

- [ ] **Step 3: Implement paper status cards, ledger views, stale-data warning, reconnect state, and guarded controls**

```tsx
<SimulationBanner persistent />
<ConnectionStatus state={session.connectionState} lastCandleAt={session.lastCandleAt} />
<EmergencyStopButton requireTypedConfirmation="STOP" />
```

- [ ] **Step 4: Run frontend and system-health tests**

Run: `docker compose run --rm web npm test -- PaperTradingPage.test.tsx`

Run: `docker compose run --rm api pytest tests/api/test_system_health.py -v`

Expected: PASS; health distinguishes application, database, worker, and market stream.

- [ ] **Step 5: Commit operational dashboard**

```bash
git add frontend/src/paper src/quant_home/api/system.py tests/api/test_system_health.py
git commit -m "feat: monitor paper trading operations"
```

### Task 5: Backup, Restore, LAN Deployment, and Final Acceptance

**Files:**
- Create: `scripts/backup.ps1`
- Create: `scripts/restore.ps1`
- Create: `docs/operations/lan-setup.md`
- Create: `docs/operations/backup-restore.md`
- Create: `frontend/e2e/paper-trading.spec.ts`
- Create: `tests/acceptance/test_fixed_dataset.py`
- Modify: `README.md`
- Modify: `compose.yaml`

**Interfaces:**
- Produces: timestamped local backup containing database dump, configuration, and dataset manifest
- Produces: restore command requiring an explicit backup path and confirmation
- Produces: final acceptance commands for backend, frontend, E2E, and fixed-dataset audit

- [ ] **Step 1: Write failing fixed-dataset and paper-flow acceptance tests**

```python
def test_verified_fixture_has_expected_fingerprint_and_summary(acceptance_runner):
    fixture = load_verified_fixture("tests/fixtures/btcusdt-1h-verified.json")
    result = acceptance_runner.run(fixture.candles)
    assert result.fingerprint == fixture.expected.dataset_fingerprint
    assert result.summary.trade_count == 12
    assert result.summary.max_drawdown == Decimal("0.0831")
```

The committed fixture contains its candles, manually audited expected fills, ending balances, dataset fingerprint, trade count `12`, and maximum drawdown `0.0831` in one reviewable JSON document.

- [ ] **Step 2: Verify acceptance tests fail before fixture and operations scripts exist**

Run: `docker compose run --rm api pytest tests/acceptance/test_fixed_dataset.py -v`

Run: `docker compose run --rm e2e npx playwright test frontend/e2e/paper-trading.spec.ts`

Expected: FAIL because the audited fixture and complete paper flow are absent.

- [ ] **Step 3: Add safe explicit-path backup and restore scripts plus LAN documentation**

```powershell
param([Parameter(Mandatory)][string]$Destination)
$resolved = [System.IO.Path]::GetFullPath($Destination)
New-Item -ItemType Directory -Force -LiteralPath $resolved | Out-Null
docker compose exec -T db pg_dump -U quant -Fc quant | Set-Content -AsByteStream -LiteralPath (Join-Path $resolved "quant.dump")
```

The restore script must resolve and display the exact backup path, reject missing manifests, create a pre-restore backup, and require the typed confirmation `RESTORE`.

- [ ] **Step 4: Run complete verification and manually audit the fixed dataset**

Run: `docker compose run --rm api pytest -q`

Run: `docker compose run --rm web npm test`

Run: `docker compose run --rm e2e npx playwright test`

Run: `docker compose config --quiet`

Expected: all commands exit 0. Manually compare every fixture signal, fill, fee, ending cash, and drawdown calculation with the committed expected rows.

- [ ] **Step 5: Commit operations and acceptance evidence**

```bash
git add scripts docs/operations frontend/e2e/paper-trading.spec.ts tests/acceptance tests/fixtures README.md compose.yaml
git commit -m "feat: complete paper trading operations"
```
