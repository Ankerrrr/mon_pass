from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from quant_home.api.auth import require_admin, require_csrf
from quant_home.auth.models import Administrator, AdminSession


router = APIRouter(prefix="/symbols", tags=["symbols"])


@router.post("/refresh")
def refresh_symbols(
    request: Request,
    _session: Annotated[AdminSession, Depends(require_csrf)],
) -> dict[str, int]:
    try:
        result = request.app.state.symbol_catalog.refresh()
    except Exception as exc:
        request.app.state.symbol_catalog_error = str(exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Binance symbol catalog refresh failed",
        ) from exc
    request.app.state.symbol_catalog_error = None
    return {"total_symbols": result.total_symbols}


@router.get("")
def list_symbols(
    request: Request,
    _administrator: Annotated[Administrator, Depends(require_admin)],
    search: Annotated[str | None, Query(max_length=40)] = None,
) -> list[dict[str, str | None]]:
    if request.app.state.symbol_catalog_error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Symbol catalog is temporarily unavailable",
        )
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
