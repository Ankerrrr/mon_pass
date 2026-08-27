from fastapi.testclient import TestClient

from quant_home.main import create_app


def test_health_identifies_simulation_mode():
    response = TestClient(create_app()).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "simulation"}
