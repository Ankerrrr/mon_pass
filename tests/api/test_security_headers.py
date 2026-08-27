from fastapi.testclient import TestClient

from quant_home.config import Settings
from quant_home.main import create_app


def test_api_sets_defensive_headers():
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
        )
    )

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
