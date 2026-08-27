from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient

from quant_home.config import Settings
from quant_home.main import create_app
from quant_home.market.candles import Candle
from quant_home.market.models import CandleDataset


class ApiCandleDownloader:
    def __init__(self):
        self.calls = []

    def fetch_candles(self, symbol, interval, start, end):
        self.calls.append((start, end))
        candles = []
        current = start
        while current < end:
            candles.append(Candle(
                open_time=current,
                open=Decimal("100"),
                high=Decimal("102"),
                low=Decimal("99"),
                close=Decimal("101"),
                volume=Decimal("10"),
                close_time=current + interval.duration - timedelta(milliseconds=1),
            ))
            current += interval.duration
        return candles


def test_dataset_lifecycle_requires_authentication_and_csrf():
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            initial_admin_username="admin",
            initial_admin_password="valid-password",
        )
    )
    app.state.candle_downloader = ApiCandleDownloader()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    payload = {
        "symbol": "BTCUSDT",
        "interval": "1h",
        "start": start.isoformat(),
        "end": (start + timedelta(hours=1)).isoformat(),
    }

    with TestClient(app) as client:
        assert client.get("/api/datasets").status_code == 401
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "valid-password"},
        )
        csrf_token = login.json()["csrf_token"]

        assert client.post("/api/datasets/refresh", json=payload).status_code == 403
        created = client.post(
            "/api/datasets/refresh",
            json=payload,
            headers={"X-CSRF-Token": csrf_token},
        )
        assert created.status_code == 201
        dataset_id = created.json()["id"]
        assert created.json()["candle_count"] == 1
        assert created.json()["is_valid"] is True

        listing = client.get("/api/datasets")
        assert listing.status_code == 200
        assert [item["id"] for item in listing.json()] == [dataset_id]

        detail = client.get(f"/api/datasets/{dataset_id}")
        assert detail.status_code == 200
        assert detail.json()["fingerprint"] == created.json()["fingerprint"]
        assert client.get(f"/api/datasets/{dataset_id}/issues").json() == []

        with app.state.session_factory() as db:
            dataset = db.get(CandleDataset, UUID(dataset_id))
            dataset.reference_count = 1
            db.commit()

        blocked = client.delete(
            f"/api/datasets/{dataset_id}",
            headers={"X-CSRF-Token": csrf_token},
        )

    assert blocked.status_code == 409


def test_dataset_api_reuses_overlap_and_rejects_misaligned_range():
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            initial_admin_username="admin",
            initial_admin_password="valid-password",
        )
    )
    downloader = ApiCandleDownloader()
    app.state.candle_downloader = downloader
    start = datetime(2026, 1, 1, tzinfo=UTC)

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "valid-password"},
        )
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        first = {
            "symbol": "BTCUSDT",
            "interval": "1h",
            "start": start.isoformat(),
            "end": (start + timedelta(hours=3)).isoformat(),
        }
        second = {
            **first,
            "start": (start + timedelta(hours=1)).isoformat(),
            "end": (start + timedelta(hours=4)).isoformat(),
        }
        assert client.post("/api/datasets/refresh", json=first, headers=headers).status_code == 201
        assert client.post("/api/datasets/refresh", json=second, headers=headers).status_code == 201

        misaligned = {
            **first,
            "start": (start + timedelta(minutes=30)).isoformat(),
        }
        assert client.post(
            "/api/datasets/refresh", json=misaligned, headers=headers
        ).status_code == 422

    assert downloader.calls == [
        (start, start + timedelta(hours=3)),
        (start + timedelta(hours=3), start + timedelta(hours=4)),
    ]
