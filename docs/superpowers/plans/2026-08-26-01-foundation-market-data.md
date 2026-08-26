# Foundation and Market Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a LAN-ready authenticated FastAPI service that catalogs Binance USDT spot symbols, caches validated candles, and runs bounded background jobs.

**Architecture:** A modular FastAPI application owns configuration, SQLAlchemy persistence, authentication, Binance public REST access, candle storage, and an in-process bounded job queue. All external responses are converted to domain DTOs before persistence.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16, HTTPX, pytest, Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-26-binance-multi-strategy-backtest-design.md`

## Global Constraints

- This phase uses Binance public market data only and stores no private Binance credential.
- One administrator account is supported; every non-health application endpoint requires authentication.
- Timestamps are UTC and candle datasets are immutable once fingerprinted.
- Unlimited symbol selection means unlimited queued units, never unlimited concurrent workers.
- The application is LAN-only and must not configure router port forwarding.

---

### Task 1: Backend Skeleton and Health Contract

**Files:**
- Create: `pyproject.toml`
- Create: `src/quant_home/__init__.py`
- Create: `src/quant_home/config.py`
- Create: `src/quant_home/main.py`
- Create: `src/quant_home/api/health.py`
- Create: `Dockerfile`
- Create: `compose.yaml`
- Create: `.gitignore`
- Test: `tests/api/test_health.py`

**Interfaces:**
- Produces: `create_app(settings: Settings | None = None) -> FastAPI`
- Produces: `GET /api/health -> {"status": "ok", "mode": "simulation"}`

- [ ] **Step 1: Write the failing health test**

```python
from fastapi.testclient import TestClient
from quant_home.main import create_app

def test_health_identifies_simulation_mode():
    response = TestClient(create_app()).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "simulation"}
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `docker compose run --rm api pytest tests/api/test_health.py -v`

Expected: FAIL because `quant_home.main` does not exist.

- [ ] **Step 3: Add minimal package, settings, app factory, and test container**

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QUANT_HOME_", env_file=".env")
    environment: Literal["test", "development", "production"] = "development"
    simulation_only: bool = True
    database_url: str = "postgresql+psycopg://quant:quant@db:5432/quant"

def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Quant Home")
    app.state.settings = settings or Settings()
    app.include_router(health.router, prefix="/api")
    return app
```

Use `python:3.12-slim` for the API image, install the project with test dependencies, and add an `api` Compose service capable of running the focused pytest command. Add `.superpowers/`, `.env`, caches, local datasets, and coverage output to `.gitignore` immediately.

- [ ] **Step 4: Run backend tests**

Run: `docker compose run --rm api pytest tests/api/test_health.py -v`

Expected: PASS.

- [ ] **Step 5: Commit the skeleton**

```bash
git add pyproject.toml src/quant_home tests/api/test_health.py Dockerfile compose.yaml .gitignore
git commit -m "feat: scaffold quant home API"
```

### Task 2: Database and Single-Administrator Authentication

**Files:**
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/0001_admin_sessions.py`
- Create: `src/quant_home/db.py`
- Create: `src/quant_home/auth/models.py`
- Create: `src/quant_home/auth/passwords.py`
- Create: `src/quant_home/auth/service.py`
- Create: `src/quant_home/api/auth.py`
- Test: `tests/auth/test_auth_service.py`
- Test: `tests/api/test_auth_api.py`

**Interfaces:**
- Produces: `hash_password(password: str) -> str`
- Produces: `verify_password(password: str, digest: str) -> bool`
- Produces: `AuthService.login(username: str, password: str, client_ip: str) -> SessionToken`
- Produces: `require_admin(request: Request, db: Session) -> Administrator`

- [ ] **Step 1: Write failing password and login-throttle tests**

```python
def test_password_digest_does_not_contain_plaintext():
    digest = hash_password("correct horse battery staple")
    assert "correct horse" not in digest
    assert verify_password("correct horse battery staple", digest)

def test_fifth_bad_login_is_rate_limited(auth_service):
    for _ in range(4):
        with pytest.raises(InvalidCredentials):
            auth_service.login("admin", "wrong", "192.168.1.20")
    with pytest.raises(LoginRateLimited):
        auth_service.login("admin", "wrong", "192.168.1.20")
```

- [ ] **Step 2: Verify the authentication tests fail**

Run: `docker compose run --rm api pytest tests/auth tests/api/test_auth_api.py -v`

Expected: FAIL because auth models and services are absent.

- [ ] **Step 3: Implement administrator, hashed passwords, server-side sessions, and throttling**

```python
class Administrator(Base):
    __tablename__ = "administrators"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str]

class AdminSession(Base):
    __tablename__ = "admin_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    administrator_id: Mapped[UUID] = mapped_column(ForeignKey("administrators.id"))
    expires_at: Mapped[datetime]
```

Use Argon2id through `pwdlib`; store only a SHA-256 hash of each random session token. Set the cookie `HttpOnly`, `SameSite=Strict`, and `Secure` only when HTTPS is configured.

- [ ] **Step 4: Add login, logout, current-user, CSRF, and protected-route tests**

Run: `docker compose run --rm api pytest tests/auth tests/api/test_auth_api.py -v`

Expected: PASS, including 401 for unauthenticated protected requests and 429 for throttled login.

- [ ] **Step 5: Commit authentication**

```bash
git add alembic.ini alembic src/quant_home/db.py src/quant_home/auth src/quant_home/api/auth.py tests/auth tests/api/test_auth_api.py
git commit -m "feat: add administrator authentication"
```

### Task 3: Binance Symbol Catalog

**Files:**
- Create: `src/quant_home/market/types.py`
- Create: `src/quant_home/market/binance_client.py`
- Create: `src/quant_home/market/catalog.py`
- Create: `src/quant_home/api/symbols.py`
- Test: `tests/market/test_catalog.py`
- Test: `tests/api/test_symbols_api.py`

**Interfaces:**
- Produces: `BinancePublicClient.exchange_info() -> dict[str, Any]`
- Produces: `SymbolCatalog.refresh() -> CatalogRefreshResult`
- Produces: `SymbolCatalog.list_usdt_spot(search: str | None) -> list[TradableSymbol]`

- [ ] **Step 1: Write a failing catalog filter test**

```python
def test_catalog_keeps_only_trading_usdt_spot_pairs(catalog, exchange_info):
    exchange_info.return_value = {
        "symbols": [
            {"symbol": "BTCUSDT", "status": "TRADING", "quoteAsset": "USDT", "isSpotTradingAllowed": True},
            {"symbol": "OLDUSDT", "status": "BREAK", "quoteAsset": "USDT", "isSpotTradingAllowed": True},
            {"symbol": "BTCFDUSD", "status": "TRADING", "quoteAsset": "FDUSD", "isSpotTradingAllowed": True},
        ]
    }
    catalog.refresh()
    assert [item.symbol for item in catalog.list_usdt_spot(None)] == ["BTCUSDT"]
```

- [ ] **Step 2: Verify catalog tests fail**

Run: `docker compose run --rm api pytest tests/market/test_catalog.py -v`

Expected: FAIL because catalog types are absent.

- [ ] **Step 3: Implement HTTP retry boundaries and catalog normalization**

```python
@dataclass(frozen=True)
class TradableSymbol:
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    price_tick: Decimal
    quantity_step: Decimal
    minimum_notional: Decimal | None
```

Retry only timeout, connection, 429, and 5xx responses with bounded exponential backoff. Do not retry invalid parameters or unknown symbols.

- [ ] **Step 4: Add authenticated search API and run tests**

Run: `docker compose run --rm api pytest tests/market/test_catalog.py tests/api/test_symbols_api.py -v`

Expected: PASS; search is case-insensitive and suspended pairs are excluded.

- [ ] **Step 5: Commit symbol catalog**

```bash
git add src/quant_home/market src/quant_home/api/symbols.py tests/market tests/api/test_symbols_api.py
git commit -m "feat: add Binance spot symbol catalog"
```

### Task 4: Candle Cache and Dataset Validation

**Files:**
- Create: `src/quant_home/market/candles.py`
- Create: `src/quant_home/market/validation.py`
- Create: `src/quant_home/market/repository.py`
- Create: `src/quant_home/market/models.py`
- Create: `src/quant_home/api/datasets.py`
- Create: `alembic/versions/0002_candle_datasets.py`
- Test: `tests/market/test_candle_validation.py`
- Test: `tests/market/test_candle_repository.py`
- Test: `tests/api/test_datasets_api.py`

**Interfaces:**
- Produces: `Candle(open_time, open, high, low, close, volume, close_time)`
- Produces: `validate_candles(candles: Sequence[Candle], interval: CandleInterval) -> ValidationReport`
- Produces: `CandleRepository.ensure_range(symbol, interval, start, end) -> CandleDataset`
- Produces: authenticated dataset list, detail, refresh, validation-issue, and delete-unused endpoints

- [ ] **Step 1: Write failing duplicate, gap, and malformed-candle tests**

```python
def test_validation_rejects_gap_and_non_positive_price():
    report = validate_candles(candles_with_gap_and_zero_close(), CandleInterval.ONE_HOUR)
    assert report.is_valid is False
    assert {issue.code for issue in report.issues} == {"MISSING_CANDLE", "NON_POSITIVE_PRICE"}
```

- [ ] **Step 2: Verify candle tests fail**

Run: `docker compose run --rm api pytest tests/market/test_candle_validation.py -v`

Expected: FAIL because candle validation is absent.

- [ ] **Step 3: Implement UTC candle types, strict validation, range reuse, and SHA-256 fingerprints**

```python
class Candle(BaseModel):
    model_config = ConfigDict(frozen=True)
    open_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: datetime

def dataset_fingerprint(candles: Sequence[Candle]) -> str:
    canonical = "\n".join(c.model_dump_json() for c in candles)
    return hashlib.sha256(canonical.encode()).hexdigest()
```

- [ ] **Step 4: Run repository and dataset API tests including overlapping-range reuse**

Run: `docker compose run --rm api pytest tests/market/test_candle_validation.py tests/market/test_candle_repository.py tests/api/test_datasets_api.py -v`

Expected: PASS, a cached overlap is not downloaded twice, and referenced datasets cannot be deleted.

- [ ] **Step 5: Commit candle storage**

```bash
git add src/quant_home/market src/quant_home/api/datasets.py alembic/versions/0002_candle_datasets.py tests/market tests/api/test_datasets_api.py
git commit -m "feat: cache and validate candle datasets"
```

### Task 5: Bounded Background Job Lifecycle

**Files:**
- Create: `src/quant_home/jobs/types.py`
- Create: `src/quant_home/jobs/models.py`
- Create: `src/quant_home/jobs/repository.py`
- Create: `src/quant_home/jobs/runner.py`
- Create: `src/quant_home/api/jobs.py`
- Create: `alembic/versions/0003_jobs.py`
- Test: `tests/jobs/test_runner.py`
- Test: `tests/api/test_jobs_api.py`

**Interfaces:**
- Produces: `JobRunner.submit(spec: JobSpec) -> UUID`
- Produces: `JobRunner.cancel(job_id: UUID) -> None`
- Produces: `JobRepository.mark_interrupted_jobs() -> int`

- [ ] **Step 1: Write failing concurrency and restart tests**

```python
async def test_runner_never_exceeds_configured_concurrency(runner, tracker):
    for index in range(20):
        await runner.submit(FakeJobSpec(index=index))
    await runner.drain()
    assert tracker.maximum_active == 3

def test_startup_marks_running_jobs_interrupted(repository):
    repository.insert(status=JobStatus.RUNNING)
    assert repository.mark_interrupted_jobs() == 1
    assert repository.latest().status is JobStatus.INTERRUPTED
```

- [ ] **Step 2: Verify runner tests fail**

Run: `docker compose run --rm api pytest tests/jobs/test_runner.py -v`

Expected: FAIL because the job state machine is absent.

- [ ] **Step 3: Implement explicit states, safe cancellation checkpoints, and semaphore-bounded execution**

```python
class JobStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    VALIDATING = "validating"
    RUNNING = "running"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
```

- [ ] **Step 4: Run job API and lifecycle tests**

Run: `docker compose run --rm api pytest tests/jobs tests/api/test_jobs_api.py -v`

Expected: PASS; cancellation prevents new units and preserves completed atomic units.

- [ ] **Step 5: Commit job lifecycle**

```bash
git add src/quant_home/jobs src/quant_home/api/jobs.py alembic/versions/0003_jobs.py tests/jobs tests/api/test_jobs_api.py
git commit -m "feat: add bounded background job runner"
```

### Task 6: Containerized LAN Development Environment

**Files:**
- Modify: `Dockerfile`
- Modify: `compose.yaml`
- Create: `.env.example`
- Modify: `.gitignore`
- Create: `README.md`
- Test: `tests/api/test_security_headers.py`

**Interfaces:**
- Produces: `docker compose up --build` development entry point
- Produces: `QUANT_HOME_BIND_HOST` and `QUANT_HOME_BIND_PORT` configuration

- [ ] **Step 1: Write a failing security-header test**

```python
def test_api_sets_defensive_headers(client):
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
```

- [ ] **Step 2: Add Docker, PostgreSQL health checks, non-root API user, and explicit bind settings**

```yaml
services:
  api:
    build: .
    environment:
      QUANT_HOME_DATABASE_URL: postgresql+psycopg://quant:${QUANT_DB_PASSWORD}@db:5432/quant
    ports:
      - "${QUANT_HOME_BIND_HOST:-127.0.0.1}:${QUANT_HOME_BIND_PORT:-8000}:8000"
  db:
    image: postgres:16-alpine
```

Set `.gitignore` to exclude `.env`, `.superpowers/`, local datasets, caches, coverage, and frontend build output.

- [ ] **Step 3: Start the stack and run migrations**

Run: `docker compose up -d --build`

Run: `docker compose run --rm api alembic upgrade head`

Expected: API and database report healthy.

- [ ] **Step 4: Run the complete foundation suite**

Run: `docker compose run --rm api pytest -q`

Expected: PASS with no warnings promoted to errors.

- [ ] **Step 5: Commit deployment foundation**

```bash
git add Dockerfile compose.yaml .env.example .gitignore README.md tests/api/test_security_headers.py src/quant_home
git commit -m "chore: add LAN development environment"
```
