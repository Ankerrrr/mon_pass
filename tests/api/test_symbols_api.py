from fastapi.testclient import TestClient

from quant_home.config import Settings
from quant_home.main import create_app
from quant_home.market.catalog import SymbolCatalog


class StubExchangeInfoClient:
    def exchange_info(self):
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
