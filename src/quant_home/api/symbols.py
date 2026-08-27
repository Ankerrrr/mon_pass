from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from quant_home.api.auth import require_admin
from quant_home.auth.models import Administrator


router = APIRouter(prefix="/symbols", tags=["symbols"])


@router.get("")
def list_symbols(
    request: Request,
    _administrator: Annotated[Administrator, Depends(require_admin)],
    search: Annotated[str | None, Query(max_length=40)] = None,
) -> list[dict[str, str | None]]:
    return [
        {
            "symbol": item.symbol,
            "base_asset": item.base_asset,
            "quote_asset": item.quote_asset,
            "status": item.status,
            "price_tick": str(item.price_tick),
            "quantity_step": str(item.quantity_step),
            "minimum_notional": (
                str(item.minimum_notional) if item.minimum_notional is not None else None
            ),
        }
        for item in request.app.state.symbol_catalog.list_usdt_spot(search)
    ]
