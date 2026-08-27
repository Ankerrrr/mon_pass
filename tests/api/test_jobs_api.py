from fastapi.testclient import TestClient

from quant_home.config import Settings
from quant_home.jobs.types import JobStatus
from quant_home.main import create_app


def test_job_inspection_and_cancellation_require_authentication_and_csrf():
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            initial_admin_username="admin",
            initial_admin_password="valid-password",
        )
    )

    with TestClient(app) as client:
        job_id = app.state.job_repository.insert(
            status=JobStatus.QUEUED,
            kind="test",
            payload={"symbols": ["BTCUSDT"]},
        )
        assert client.get("/api/jobs").status_code == 401

        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "valid-password"},
        )
        csrf_token = login.json()["csrf_token"]

        listing = client.get("/api/jobs")
        assert listing.status_code == 200
        assert listing.json()[0]["id"] == str(job_id)
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "queued"

        assert client.post(f"/api/jobs/{job_id}/cancel").status_code == 403
        cancelled = client.post(
            f"/api/jobs/{job_id}/cancel",
            headers={"X-CSRF-Token": csrf_token},
        )

        assert cancelled.status_code == 202
        assert app.state.job_repository.get(job_id).cancel_requested is True
