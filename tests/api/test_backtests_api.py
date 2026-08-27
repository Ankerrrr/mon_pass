import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from uuid import UUID

from fastapi.testclient import TestClient

from quant_home.backtest.engine import BacktestResult
from quant_home.backtest.ledger import Ledger
from quant_home.backtest.repository import BacktestRepository
from quant_home.backtest.types import Fill, StrategyKind
from quant_home.config import Settings
from quant_home.main import create_app
from quant_home.market.candles import Candle


class BacktestCandleDownloader:
    def __init__(self, *, incomplete: bool = False) -> None:
        self.incomplete = incomplete

    def fetch_candles(self, symbol, interval, start, end):
        candles = []
        current = start
        while current < end:
            candles.append(
                Candle(
                    open_time=current,
                    open=Decimal("100"),
                    high=Decimal("102"),
                    low=Decimal("99"),
                    close=Decimal("101"),
                    volume=Decimal("10"),
                    close_time=current + interval.duration - timedelta(milliseconds=1),
                )
            )
            current += interval.duration
        return candles[:-1] if self.incomplete else candles


def _app(*, incomplete_data: bool = False):
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            initial_admin_username="admin",
            initial_admin_password="valid-password",
        )
    )
    app.state.candle_downloader = BacktestCandleDownloader(
        incomplete=incomplete_data
    )
    return app


def _login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "valid-password"},
    )
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def _configuration_payload() -> dict[str, object]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    universe = {"symbols": [{"symbol": "BTCUSDT", "weight": "1"}]}
    return {
        "initial_capital": "10000",
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=8)).isoformat(),
        "universes": {
            "trend": dict(universe),
            "mean_reversion": dict(universe),
            "grid": dict(universe),
        },
    }


def _create_configuration(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/configurations",
        headers=headers,
        json={"name": "Production", "payload": _configuration_payload()},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_runs_in_background_and_exposes_result_by_run_and_job_id():
    app = _app()
    with TestClient(app) as client:
        assert client.get("/api/backtests").status_code == 401
        headers = _login(client)
        configuration_id = _create_configuration(client, headers)

        assert client.post(
            "/api/backtests", json={"configuration_id": configuration_id}
        ).status_code == 403
        created = client.post(
            "/api/backtests",
            headers=headers,
            json={"configuration_id": configuration_id},
        )
        assert created.status_code == 202
        job_id = created.json()["job_id"]
        client.portal.call(app.state.job_runner.drain)

        job = app.state.job_repository.get(UUID(job_id))
        assert job.status.value == "completed"
        by_job = client.get(f"/api/backtests/jobs/{job_id}")
        assert by_job.status_code == 200
        run_id = by_job.json()["id"]
        assert by_job.json()["job_id"] == job_id
        assert by_job.json()["configuration_snapshot"]["initial_capital"] == "10000"
        assert set(by_job.json()["dataset_fingerprints"]) == {
            "trend",
            "mean_reversion",
            "grid",
        }
        assert set(by_job.json()["result_snapshot"]["ledgers"]) == {
            "trend",
            "mean_reversion",
            "grid",
        }

        listing = client.get("/api/backtests")
        assert [item["id"] for item in listing.json()] == [run_id]
        assert client.get(f"/api/backtests/{run_id}").json() == by_job.json()


def test_duplicate_configuration_requires_explicit_confirmation():
    app = _app()
    with TestClient(app) as client:
        headers = _login(client)
        configuration_id = _create_configuration(client, headers)
        request = {"configuration_id": configuration_id}

        first = client.post("/api/backtests", headers=headers, json=request)
        duplicate = client.post("/api/backtests", headers=headers, json=request)
        confirmed = client.post(
            "/api/backtests",
            headers=headers,
            json={**request, "confirm_duplicate": True},
        )

        assert first.status_code == 202
        assert duplicate.status_code == 409
        assert confirmed.status_code == 202
        assert confirmed.json()["job_id"] != first.json()["job_id"]
        client.portal.call(app.state.job_runner.drain)


def test_invalid_downloaded_dataset_fails_without_saving_a_run():
    app = _app(incomplete_data=True)
    with TestClient(app) as client:
        headers = _login(client)
        configuration_id = _create_configuration(client, headers)
        created = client.post(
            "/api/backtests",
            headers=headers,
            json={"configuration_id": configuration_id},
        )
        job_id = created.json()["job_id"]
        client.portal.call(app.state.job_runner.drain)

        job = app.state.job_repository.get(UUID(job_id))
        assert job.status.value == "failed"
        assert "invalid candle dataset" in job.error.lower()
        assert client.get(f"/api/backtests/jobs/{job_id}").status_code == 404
        assert client.get("/api/backtests").json() == []


def test_trade_csv_combines_fills_from_every_strategy():
    app = _app()
    with TestClient(app) as client:
        _login(client)
        ledgers = {
            StrategyKind.TREND: Ledger(Decimal("400")),
            StrategyKind.MEAN_REVERSION: Ledger(Decimal("300")),
            StrategyKind.GRID: Ledger(Decimal("200")),
        }
        for index, kind in enumerate(StrategyKind, start=1):
            ledgers[kind].apply(
                Fill.buy(
                    "BTCUSDT",
                    quantity=Decimal("0.1"),
                    price=Decimal(str(100 + index)),
                    fee=Decimal("0.01"),
                )
            )
        run_id = BacktestRepository(app.state.session_factory).save_completed(
            BacktestResult(ledgers, Decimal("100"), "f" * 64, "1"),
            configuration_snapshot={"name": "all fills"},
            dataset_fingerprints={},
        )

        response = client.get(f"/api/backtests/{run_id}/trades.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(StringIO(response.text)))
    assert [row["strategy"] for row in rows] == [
        "grid",
        "mean_reversion",
        "trend",
    ]
    assert [row["price"] for row in rows] == ["103", "102", "101"]
