from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from quant_home.config import Settings
from quant_home.main import create_app


def test_authenticated_paper_lifecycle_is_idempotent_and_audited():
    app = create_app(Settings(
        environment="test", database_url="sqlite+pysqlite:///:memory:",
        initial_admin_username="admin", initial_admin_password="valid-password",
    ))
    with TestClient(app) as client:
        assert client.get("/api/paper").status_code == 401
        login = client.post("/api/auth/login", json={"username": "admin", "password": "valid-password"})
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        start = datetime(2026, 1, 1, tzinfo=UTC)
        universe = {"symbols": [{"symbol": "BTCUSDT", "weight": "1"}]}
        config = client.post("/api/configurations", headers=headers, json={
            "name": "paper-api", "payload": {
                "initial_capital": "10000", "start_time": start.isoformat(),
                "end_time": (start + timedelta(days=1)).isoformat(),
                "universes": {"trend": universe, "mean_reversion": universe, "grid": universe},
            },
        })
        created = client.post("/api/paper", headers=headers, json={"configuration_id": config.json()["id"]})
        assert created.status_code == 201
        session_id = created.json()["id"]
        assert client.get("/api/paper").json()[0]["status"] == "active"
        assert client.post(f"/api/paper/{session_id}/stop", headers=headers).json() == {"stopped": True}
        assert client.post(f"/api/paper/{session_id}/stop", headers=headers).json() == {"stopped": False}
        actions = [item["action"] for item in client.get("/api/paper/audit/events").json()]
        assert actions == ["PAPER_STOP", "PAPER_STOP", "PAPER_START", "CONFIGURATION_CREATE"]
