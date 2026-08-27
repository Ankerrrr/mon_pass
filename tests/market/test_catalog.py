from decimal import Decimal

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
                },
                {
                    "symbol": "OLDUSDT",
                    "status": "BREAK",
                    "baseAsset": "OLD",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                    "filters": [],
                },
                {
                    "symbol": "BTCFDUSD",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "FDUSD",
                    "isSpotTradingAllowed": True,
                    "filters": [],
                },
                {
                    "symbol": "NOUSDT",
                    "status": "TRADING",
                    "baseAsset": "NO",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": False,
                    "filters": [],
                },
            ]
        }


def test_catalog_keeps_only_trading_usdt_spot_pairs():
    catalog = SymbolCatalog(StubExchangeInfoClient())

    result = catalog.refresh()
    symbols = catalog.list_usdt_spot(None)

    assert result.total_symbols == 1
    assert [item.symbol for item in symbols] == ["BTCUSDT"]
    assert symbols[0].price_tick == Decimal("0.01000000")
    assert symbols[0].quantity_step == Decimal("0.00001000")
    assert symbols[0].minimum_notional == Decimal("5.00000000")


def test_catalog_search_is_case_insensitive():
    catalog = SymbolCatalog(StubExchangeInfoClient())
    catalog.refresh()

    assert [item.symbol for item in catalog.list_usdt_spot("btc")] == ["BTCUSDT"]
