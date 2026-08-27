from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from quant_home.api.auth import require_admin
from quant_home.db import get_db


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def system_health(request: Request, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    database = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database = "error"
    supervisor = request.app.state.paper_supervisor
    stale = supervisor.last_cycle_at is None or (datetime.now(UTC) - supervisor.last_cycle_at).total_seconds() > 60
    return {
        "application": "ok", "database": database,
        "paper_worker": "error" if supervisor.last_error else "starting" if supervisor.last_cycle_at is None else "ok",
        "market_stream": "stale" if stale else "connected",
        "last_market_cycle_at": supervisor.last_cycle_at.isoformat() if supervisor.last_cycle_at else None,
        "error": supervisor.last_error,
        "mode": "simulation",
    }
