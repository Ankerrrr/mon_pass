from fastapi.testclient import TestClient

from quant_home.config import Settings
from quant_home.main import create_app
from quant_home.market.catalog import SymbolCatalog


class StubExchangeInfoClient:
    def __init__(self):
        self.calls = 0

    def exchange_info(self):
        self.calls += 1
        return {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.01000000"},
                        {"filterType": "LOT_SIZE", "stepSize": "0.00001000"},
                        {"filterType": "MIN_NOTIONAL", "minNotional": "5.00000000"},
                    ],
                }
            ]
        }


def test_symbol_search_requires_authentication_and_filters_case_insensitively():
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            initial_admin_username="admin",
            initial_admin_password="valid-password",
        )
    )
    catalog = SymbolCatalog(StubExchangeInfoClient())
    catalog.refresh()
    app.state.symbol_catalog = catalog

    with TestClient(app) as client:
        assert client.get("/api/symbols").status_code == 401
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "valid-password"},
        )
        assert login.status_code == 200

        response = client.get("/api/symbols", params={"search": "btc"})

    assert response.status_code == 200
    assert response.json() == [
        {
            "symbol": "BTCUSDT",
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "status": "TRADING",
            "price_tick": "0.01000000",
            "quantity_step": "0.00001000",
            "minimum_notional": "5.00000000",
        }
    ]


def test_startup_refreshes_symbol_catalog():
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            initial_admin_username="admin",
            initial_admin_password="valid-password",
            refresh_symbol_catalog_on_startup=True,
        )
    )
    source = StubExchangeInfoClient()
    app.state.symbol_catalog = SymbolCatalog(source)

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "valid-password"},
        )
        response = client.get("/api/symbols")

    assert login.status_code == 200
    assert response.status_code == 200
    assert [item["symbol"] for item in response.json()] == ["BTCUSDT"]
    assert source.calls == 1


def test_administrator_can_refresh_symbol_catalog_with_csrf():
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            initial_admin_username="admin",
            initial_admin_password="valid-password",
        )
    )
    source = StubExchangeInfoClient()
    app.state.symbol_catalog = SymbolCatalog(source)

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "valid-password"},
        )
        assert client.post("/api/symbols/refresh").status_code == 403
        refreshed = client.post(
            "/api/symbols/refresh",
            headers={"X-CSRF-Token": login.json()["csrf_token"]},
        )

    assert refreshed.status_code == 200
    assert refreshed.json() == {"total_symbols": 1}
    assert source.calls == 1


def test_catalog_failure_is_reported_as_degraded_service():
    app = create_app(
        Settings(
            environment="test",
            database_url="sqlite+pysqlite:///:memory:",
            initial_admin_username="admin",
            initial_admin_password="valid-password",
        )
    )
    app.state.symbol_catalog_error = "upstream unavailable"

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "valid-password"},
        )
        response = client.get("/api/symbols")

    assert login.status_code == 200
    assert response.status_code == 503
    assert "upstream unavailable" not in response.text
