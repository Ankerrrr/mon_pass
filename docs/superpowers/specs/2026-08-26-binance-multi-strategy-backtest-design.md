# Binance Multi-Strategy Backtest System Design

Date: 2026-08-26  
Approved: 2026-08-27
Status: Approved for full first-release implementation

## 1. Purpose

Build a personal, LAN-accessible quantitative trading research system for Binance Spot markets. The first release supports historical backtesting and real-time paper trading only. It does not place real orders or require a private Binance API key.

The system lets one administrator select any number of Binance USDT spot pairs, run three strategies concurrently with independent virtual ledgers, adjust all meaningful parameters in the web interface, and compare strategy, symbol, and combined portfolio performance.

The system is a research and risk-control tool. It does not promise profit or guarantee buying at the lowest price and selling at the highest price.

## 2. Scope

### 2.1 Included

- Historical Binance Spot market-data download and local caching.
- Searchable selection of any currently tradable Binance USDT spot pairs.
- Trend-following, mean-reversion, and grid strategies.
- Independent timeframe and independent virtual ledger for each strategy.
- Manual allocation among the three strategies and a cash reserve.
- Automatic equal symbol weights with optional manual overrides inside each strategy.
- Adjustable strategy, execution, fee, slippage, and risk parameters.
- Queued backtests with progress, cancellation, and recoverable interrupted status.
- Aggregate and per-strategy performance dashboards.
- Real-time paper trading using public market data.
- CSV export of trades and performance results.
- Single-administrator authentication for LAN access.
- Docker-based local deployment.

### 2.2 Excluded from the First Release

- Real-money order placement.
- Futures, margin, leverage, lending, or short selling.
- Custody or management of another person's funds.
- Public internet exposure, multi-user accounts, subscriptions, or paid services.
- Machine-learning strategy generation or automatic parameter optimization.
- Automatic strategy switching or performance-based capital reallocation.

## 3. Selected Architecture

Use a modular monolith packaged as one deployable project:

- React provides the responsive browser interface and charts.
- FastAPI provides authentication, configuration, market-data, backtest, paper-trading, and reporting APIs.
- A background worker inside the application process executes queued downloads and backtests with bounded concurrency.
- A relational database stores users, configurations, jobs, data metadata, virtual ledgers, trades, and results.
- Historical candle files may use a compact columnar format while the database stores metadata and references.
- Docker Compose starts the web application and database on the home computer.

Modules communicate through explicit service interfaces inside one codebase. Strategy code cannot call Binance or write directly to the database. It receives validated candles and parameters, then emits deterministic signals.

## 4. Main Modules

### 4.1 Authentication

- Supports one administrator account.
- Stores a password hash, never the original password.
- Issues server-side sessions with expiration.
- Rate-limits repeated failed logins.
- Requires authentication for every configuration, job, result, and paper-trading endpoint.

### 4.2 Symbol Catalog

- Reads Binance exchange information through public endpoints.
- Includes only currently tradable USDT spot pairs.
- Supports search and optional liquidity filtering.
- Marks suspended or removed pairs and prevents new runs from using them.
- Does not silently alter historical runs when a symbol later becomes unavailable.

### 4.3 Market Data

- Downloads candles by symbol, interval, and date range.
- Caches data locally and reuses overlapping ranges.
- Normalizes timestamps to UTC.
- Detects duplicate, missing, unordered, non-positive, and malformed candles.
- Stops affected ranges when material gaps remain after a bounded retry; it does not invent prices.
- Records data source, download time, interval, range, and dataset fingerprint.

### 4.4 Strategy Engine

Implements a common strategy interface with validated parameter schemas. Each strategy receives only candles available at the decision timestamp and emits target actions without performing accounting.

The three strategies are:

1. Trend following.
2. Mean reversion.
3. Grid trading.

### 4.5 Backtest Engine

- Processes signals in chronological order.
- Maintains independent virtual cash, positions, trades, and equity for every strategy.
- Applies execution assumptions, fees, slippage, and risk decisions consistently.
- Produces deterministic results for the same dataset, engine version, and parameter snapshot.
- Runs symbols in a bounded queue so an unlimited selection does not create unlimited simultaneous work.
- Allows cancellation between safe processing checkpoints.

### 4.6 Portfolio Risk

- Validates strategy allocations plus cash reserve total exactly 100%.
- Validates symbol weights inside each strategy total exactly 100% when symbols are selected.
- Enforces per-symbol exposure, per-strategy exposure, total exposure, loss, and drawdown limits.
- Prevents negative cash and selling more than the strategy ledger owns.
- Stops new entries when a configured limit is breached while still allowing risk-reducing exits.

### 4.7 Paper Trading

- Uses public real-time market data and the same strategy, execution, accounting, and risk interfaces as backtesting.
- Keeps paper ledgers separate from historical backtest ledgers.
- Clearly labels every screen as simulation mode.
- Restores state after restart from persisted checkpoints and reconciles candle gaps before resuming signals.

### 4.8 Reporting

- Shows combined, strategy, and symbol views.
- Stores immutable run metadata, parameters, dataset fingerprint, and application version.
- Exports trades and summary metrics to CSV.
- Compares each result with buy-and-hold over the same symbol and period where meaningful.

## 5. Capital Allocation

The administrator manually assigns percentages to:

- Trend following.
- Mean reversion.
- Grid trading.
- Cash reserve.

The total must equal 100%. A default profile uses 40% trend, 30% mean reversion, 20% grid, and 10% reserve.

Within each strategy, selected symbols initially receive equal weights. The administrator can override individual weights or restore equal allocation with one action. Each strategy's symbol weights must total 100%.

Strategies maintain independent virtual ledgers even when they trade the same symbol in opposite directions. Aggregate reporting sums their marked-to-market equity but preserves attribution to each strategy.

## 6. Timeframes and Symbol Selection

- The administrator may select any number of supported USDT spot pairs.
- The interface estimates data volume and expected runtime before starting.
- The server limits concurrent downloads and backtest workers; excess work remains queued.
- Each strategy has one independently adjustable candle interval applied to its selected symbols for that run.
- Default intervals are 4h for trend following, 1h for mean reversion, and 15m for grid trading.

## 7. Strategy Parameters

Every parameter has a type, valid range, help text, default value, and server-side validation. Configurations can be named, cloned, exported, imported, and restored to defaults.

### 7.1 Trend Following

- Moving-average type.
- Fast and slow periods, with fast strictly less than slow.
- Breakout confirmation candle count.
- Fixed stop-loss percentage.
- Trailing-stop percentage.
- Take-profit percentage or disabled state.
- Per-entry allocation percentage.
- Cooldown candle count.

Default profile: EMA 20/50, one confirmation candle, 3% fixed stop, 5% trailing stop, and no mandatory take profit.

### 7.2 Mean Reversion

- RSI period.
- RSI entry and exit thresholds, with entry below exit.
- Bollinger period and standard-deviation multiplier.
- Number of staged entries.
- Distance between staged entries.
- Maximum holding candles.
- Stop-loss and take-profit percentages.

Default profile: RSI 14, entry below 30, exit above 55, Bollinger 20 with two standard deviations, and bounded staged entries.

### 7.3 Grid Trading

- Lower and upper bounds, with lower strictly below upper.
- Grid count.
- Arithmetic or geometric spacing.
- Capital per grid or proportional allocation.
- Maximum inventory percentage.
- Out-of-range action: stop entries, close, or recalculate.
- Stop-loss percentage.
- Re-grid cooldown candles.

The default out-of-range action stops new entries and preserves the current ledger for explicit review. Automatic re-gridding is available but not the default.

## 8. Execution Model

- Strategies make decisions only after a candle closes.
- A standard market-style signal fills at the next candle open, adjusted by configured slippage and fees.
- Limit and grid fills require the subsequent candle range to cross the order price.
- A configurable conservative fill policy controls ambiguous candles.
- If stop-loss and take-profit are both touched in one candle and intrabar order is unknown, the adverse outcome is applied by default.
- Orders cannot exceed available strategy cash or position quantity.
- Partial-fill simulation is excluded from the first release; each eligible simulated order is fully filled subject to available cash and inventory.
- Fees and slippage are applied to every simulated fill and included in ledger reconciliation.

## 9. Backtest Configuration and Results

Each run snapshots:

- Initial capital.
- Selected symbols and symbol weights.
- Strategy allocations and cash reserve.
- Strategy intervals and parameters.
- Date range.
- Fee, slippage, and execution policy.
- Risk limits.
- Dataset fingerprint and engine version.

Reported metrics include:

- Total and annualized return.
- Maximum drawdown.
- Win rate and profit factor.
- Sharpe ratio using a documented calculation convention.
- Trade count and average holding duration.
- Total fees and simulated slippage.
- Current and peak exposure.
- Equity and drawdown curves.
- Per-strategy and per-symbol attribution.
- Buy-and-hold comparison.

Old results remain immutable when a configuration is later edited.

## 10. Web Interface

The responsive interface contains:

- Overview.
- Create Backtest.
- Backtest Results.
- Strategy Settings.
- Paper Trading.
- Trade History.
- Data Management.
- System Settings.

The overview shows combined return, drawdown, trade count, exposure, equity curve, benchmark comparison, strategy allocation, and strategy status cards.

Desktop uses a left navigation rail and multi-column dashboard. Mobile uses a compact menu and single-column cards. Simulation mode is always visible.

## 11. Job Lifecycle

Jobs use these states:

- Queued.
- Downloading data.
- Validating data.
- Running.
- Aggregating.
- Completed.
- Failed.
- Cancelled.
- Interrupted.

Progress reports the current stage and completed symbols. Cancellation marks completed atomic work and prevents new units from starting. A restart marks active jobs interrupted; the administrator may restart them as a new run using the same parameter snapshot.

## 12. Error Handling

- Binance timeouts and transient server errors receive bounded exponential backoff.
- Rate-limit responses pause affected work according to server guidance.
- Permanent symbol or parameter errors fail only the affected unit and appear in a run summary.
- Database writes use transactions so partial results are not presented as complete.
- User-facing messages describe the action needed; technical details remain in structured logs.
- Repeated identical job submissions are detected and require explicit confirmation.
- One failed symbol does not terminate unrelated symbol work unless the administrator selects fail-fast behavior.

## 13. Security

- The application is intended for a trusted home LAN and is not automatically exposed through the router.
- Passwords use a current adaptive password-hashing algorithm.
- Sessions use HTTP-only cookies and appropriate same-site protection.
- State-changing requests require CSRF protection.
- Inputs are schema-validated and rendered without unsafe HTML.
- Authentication and sensitive actions are audit logged.
- Phase one stores no Binance private credentials.
- A future live-trading phase must keep API credentials server-side, separate read and trade permissions where practical, restrict source IPs, and prohibit withdrawal permission.

## 14. Persistence Model

Core entities are:

- Administrator.
- Session.
- Symbol metadata.
- Candle dataset metadata.
- Strategy configuration.
- Strategy allocation.
- Symbol allocation.
- Backtest run.
- Backtest job unit.
- Virtual ledger.
- Virtual order and fill.
- Position.
- Equity point.
- Performance summary.
- Paper-trading session.
- Audit event.

Large candle and equity series may be stored outside ordinary relational rows when profiling shows a clear benefit. Database metadata remains the source of truth for identity and versioning.

## 15. Deployment

- Docker Compose starts the application and relational database.
- Configuration uses environment variables or mounted local secrets.
- The application binds to a configurable LAN interface.
- The setup guide explains firewall rules without enabling router port forwarding.
- Health endpoints report application, database, worker, and market-data status.
- Database and configuration backups can be created and restored locally.

## 16. Testing

### 16.1 Unit Tests

- Deterministic signals for all three strategies.
- Parameter boundary validation.
- Ledger cash, position, fee, and profit-and-loss conservation.
- Risk-limit decisions.
- Execution behavior for gaps and ambiguous candles.
- Performance metric calculations.

### 16.2 Integration Tests

- Public Binance client with mocked success, timeout, malformed data, unavailable symbol, and rate-limit responses.
- Database transactions and immutable run snapshots.
- Authentication, authorization, session expiration, and login throttling.
- Full create, execute, cancel, inspect, and export workflow.

### 16.3 Regression and Property Tests

- Fixed datasets produce fixed trades and metrics.
- Strategies cannot access candles after the decision timestamp.
- Cash and inventory never become negative.
- Allocations outside valid totals are rejected.
- Results remain deterministic across repeated runs.

### 16.4 UI and Performance Tests

- Desktop and mobile critical flows.
- Form validation and parameter restoration.
- Large symbol selections remain queued and do not block normal UI requests.
- Dashboard remains responsive while background jobs run.

## 17. Acceptance Criteria

The first release is accepted when:

1. The administrator can log in from another device on the same LAN.
2. The administrator can search and select any number of current Binance USDT spot pairs.
3. All three strategies can run concurrently with independent ledgers and independent intervals.
4. Strategy and symbol allocations are adjustable and validated.
5. Every documented parameter is adjustable and persisted.
6. A backtest can be queued, observed, cancelled, and inspected.
7. Results include trades, metrics, equity, drawdown, attribution, and buy-and-hold comparison.
8. Fees, slippage, next-candle execution, and conservative ambiguous-candle handling affect results correctly.
9. Fixed regression data produces verified deterministic output.
10. Paper trading uses the same strategy and accounting rules without placing real orders.
11. No Binance private API credential is required or stored.
12. Automated tests and a manual fixed-dataset audit pass.

## 18. Future Extension Boundary

Real-money trading is a separate project phase. It requires a dedicated design review covering exchange authentication, order idempotency, reconciliation, clock synchronization, partial fills, exchange filters, emergency shutdown, monitoring, credential rotation, and operational/legal readiness. Approval of this document does not approve live trading.

## 19. Delivery Sequence and Gates

The complete first release is delivered sequentially so downstream interfaces build on verified foundations:

1. Complete the deterministic backtest domain, persistence, API, reporting, and named configuration support.
2. Complete the authenticated responsive web dashboard and the end-to-end backtest workflow.
3. Complete restart-safe public-data paper trading, audit controls, operational health, backup, and restore.
4. Run the full backend, frontend, browser, migration, fixed-dataset, and Docker Compose acceptance suite.

Each phase must pass its focused tests, the accumulated regression suite, and a code review before the next phase begins. The application must remain runnable at every phase boundary. Paper trading may reuse only the already-tested strategy, execution, ledger, and risk interfaces; it must not create a parallel accounting implementation.

The existing migration head is `0004_dataset_identity`. New revisions are allocated without renaming applied history:

- `0005_backtests`
- `0006_strategy_configurations`
- `0007_paper_sessions`
- `0008_audit_events`

The release remains simulation-only throughout development and acceptance. No implementation step may introduce Binance private credentials, signed endpoints, or real-order capability.
