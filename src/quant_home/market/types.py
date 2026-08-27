from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TradableSymbol:
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    price_tick: Decimal
    quantity_step: Decimal
    minimum_notional: Decimal | None


@dataclass(frozen=True)
class CatalogRefreshResult:
    total_symbols: int
