from fastapi.testclient import TestClient

from quant_home.config import Settings
from quant_home.main import create_app


class CloseTracker:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_app_closes_market_client_on_shutdown():
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
        )
    )
    tracker = CloseTracker()
    app.state.market_client = tracker

    with TestClient(app):
        assert tracker.closed is False

    assert tracker.closed is True
