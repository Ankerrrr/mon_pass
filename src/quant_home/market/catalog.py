from decimal import Decimal
from typing import Any, Protocol

from quant_home.market.types import CatalogRefreshResult, TradableSymbol


class ExchangeInfoClient(Protocol):
    def exchange_info(self) -> dict[str, Any]: ...


class SymbolCatalog:
    def __init__(self, client: ExchangeInfoClient) -> None:
        self.client = client
        self._symbols: tuple[TradableSymbol, ...] = ()

    def refresh(self) -> CatalogRefreshResult:
        normalized: list[TradableSymbol] = []
        for raw in self.client.exchange_info().get("symbols", []):
            if not (
                raw.get("status") == "TRADING"
                and raw.get("quoteAsset") == "USDT"
                and raw.get("isSpotTradingAllowed") is True
            ):
                continue
            filters = {item["filterType"]: item for item in raw.get("filters", [])}
            normalized.append(
                TradableSymbol(
                    symbol=raw["symbol"],
                    base_asset=raw["baseAsset"],
                    quote_asset=raw["quoteAsset"],
                    status=raw["status"],
                    price_tick=Decimal(filters["PRICE_FILTER"]["tickSize"]),
                    quantity_step=Decimal(filters["LOT_SIZE"]["stepSize"]),
                    minimum_notional=self._minimum_notional(filters),
                )
            )
        self._symbols = tuple(sorted(normalized, key=lambda item: item.symbol))
        return CatalogRefreshResult(total_symbols=len(self._symbols))

    def list_usdt_spot(self, search: str | None) -> list[TradableSymbol]:
        if not search:
            return list(self._symbols)
        term = search.casefold()
        return [
            item
            for item in self._symbols
            if term in item.symbol.casefold() or term in item.base_asset.casefold()
        ]

    @staticmethod
    def _minimum_notional(filters: dict[str, dict[str, Any]]) -> Decimal | None:
        minimum = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL")
        if minimum is None:
            return None
        value = minimum.get("minNotional")
        return Decimal(value) if value is not None else None
