from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from quant_home.api import configurations
from quant_home.config import Settings
from quant_home.configurations.models import StrategyConfiguration
from quant_home.main import create_app


def _payload(*, fast_period: int = 20) -> dict[str, object]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    universe = {
        "symbols": [{"symbol": "BTCUSDT", "weight": "1"}],
    }
    return {
        "initial_capital": "10000",
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(days=30)).isoformat(),
        "allocations": {
            "trend": "0.40",
            "mean_reversion": "0.30",
            "grid": "0.20",
            "cash_reserve": "0.10",
        },
        "universes": {
            "trend": dict(universe),
            "mean_reversion": dict(universe),
            "grid": dict(universe),
        },
        "trend": {"fast_period": fast_period, "slow_period": 50},
        "mean_reversion": {},
        "grid": {},
        "fee_rate": "0.001",
        "slippage_bps": "5",
    }


def _client() -> tuple[TestClient, object]:
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            initial_admin_username="admin",
            initial_admin_password="valid-password",
        )
    )
    if not any(
        getattr(route, "path", None) == "/api/configurations" for route in app.routes
    ):
        app.include_router(configurations.router, prefix="/api")
    return TestClient(app), app


def _login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "valid-password"},
    )
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_configuration_lifecycle_preserves_immutable_versions():
    client, _app = _client()
    with client:
        assert client.get("/api/configurations").status_code == 401
        headers = _login(client)
        created = client.post(
            "/api/configurations",
            json={"name": "Balanced", "description": "base", "payload": _payload()},
            headers=headers,
        )
        assert created.status_code == 201
        configuration_id = created.json()["id"]
        assert created.json()["version"] == 1
        assert created.json()["payload"]["universes"]["trend"]["interval"] == "4h"

        updated = client.put(
            f"/api/configurations/{configuration_id}",
            json={
                "name": "Balanced tuned",
                "description": "tuned",
                "payload": _payload(fast_period=25),
            },
            headers=headers,
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2
        assert updated.json()["payload"]["trend"]["fast_period"] == 25

        original = client.get(
            f"/api/configurations/{configuration_id}", params={"version": 1}
        )
        assert original.status_code == 200
        assert original.json()["version"] == 1
        assert original.json()["name"] == "Balanced"
        assert original.json()["description"] == "base"
        assert original.json()["payload"]["trend"]["fast_period"] == 20

        listing = client.get("/api/configurations")
        assert [(item["name"], item["version"]) for item in listing.json()] == [
            ("Balanced tuned", 2)
        ]

        cloned = client.post(
            f"/api/configurations/{configuration_id}/clone",
            json={"name": "Balanced copy"},
            headers=headers,
        )
        assert cloned.status_code == 201
        assert cloned.json()["id"] != configuration_id
        assert cloned.json()["version"] == 1
        assert cloned.json()["payload"] == updated.json()["payload"]

        exported = client.get(f"/api/configurations/{configuration_id}/export")
        assert exported.status_code == 200
        imported = client.post(
            "/api/configurations/import",
            json={**exported.json(), "name": "Imported"},
            headers=headers,
        )
        assert imported.status_code == 201
        assert imported.json()["payload"] == updated.json()["payload"]

        deleted = client.delete(
            f"/api/configurations/{configuration_id}", headers=headers
        )
        assert deleted.status_code == 204
        assert client.get(f"/api/configurations/{configuration_id}").status_code == 404


def test_invalid_create_and_import_do_not_write_configuration():
    client, app = _client()
    with client:
        headers = _login(client)
        invalid = _payload()
        invalid["trend"] = {"fast_period": 50, "slow_period": 20}

        created = client.post(
            "/api/configurations",
            json={"name": "Invalid", "payload": invalid},
            headers=headers,
        )
        imported = client.post(
            "/api/configurations/import",
            json={"name": "Invalid import", "payload": invalid},
            headers=headers,
        )

        assert created.status_code == 422
        assert imported.status_code == 422
        assert client.get("/api/configurations").json() == []
        with app.state.session_factory() as db:
            assert db.query(StrategyConfiguration).count() == 0


def test_defaults_are_authenticated_and_backtest_compatible():
    client, _app = _client()
    with client:
        assert client.get("/api/configurations/defaults").status_code == 401
        _login(client)
        response = client.get("/api/configurations/defaults")

    assert response.status_code == 200
    assert response.json()["intervals"] == {
        "trend": "4h",
        "mean_reversion": "1h",
        "grid": "15m",
    }
    assert response.json()["trend"]["fast_period"] == 20
