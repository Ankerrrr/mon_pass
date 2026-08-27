from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from quant_home.api.auth import require_admin, require_csrf
from quant_home.audit.service import AuditService
from quant_home.auth.models import Administrator, AdminSession
from quant_home.configurations.repository import ConfigurationNotFound
from quant_home.db import get_db
from quant_home.paper.models import PaperSession
from quant_home.paper.repository import PaperRepository, PaperSessionNotFound
from quant_home.paper.service import PaperTradingService


router = APIRouter(prefix="/paper", tags=["paper trading"])
Database = Annotated[Session, Depends(get_db)]
Authenticated = Annotated[Administrator, Depends(require_admin)]
CsrfProtected = Annotated[AdminSession, Depends(require_csrf)]


class StartPaperRequest(BaseModel):
    configuration_id: UUID
    configuration_version: int | None = None


def _json(item: PaperSession) -> dict[str, object]:
    return {
        "id": str(item.id), "configuration_id": str(item.configuration_id) if item.configuration_id else None,
        "configuration_version": item.configuration_version,
        "configuration_snapshot": item.configuration_snapshot, "state_snapshot": item.state_snapshot,
        "status": item.status.value, "connection_state": item.connection_state.value,
        "last_candle_at": item.last_candle_at.isoformat() if item.last_candle_at else None,
        "error": item.error, "created_at": item.created_at.isoformat(),
        "stopped_at": item.stopped_at.isoformat() if item.stopped_at else None,
    }


@router.get("")
def list_sessions(request: Request, _admin: Authenticated) -> list[dict[str, object]]:
    return [_json(item) for item in PaperRepository(request.app.state.session_factory).list()]


@router.get("/{session_id}")
def session_detail(session_id: UUID, request: Request, _admin: Authenticated) -> dict[str, object]:
    try:
        return _json(PaperRepository(request.app.state.session_factory).get(session_id))
    except PaperSessionNotFound as exc:
        raise HTTPException(status_code=404) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def start_session(payload: StartPaperRequest, db: Database, session: CsrfProtected) -> dict[str, str]:
    try:
        session_id = PaperTradingService(db).start(payload.configuration_id, payload.configuration_version)
    except ConfigurationNotFound as exc:
        raise HTTPException(status_code=404) from exc
    AuditService(db).record(session.administrator_id, "PAPER_START", "paper_session", str(session_id))
    return {"id": str(session_id)}


@router.post("/{session_id}/stop")
def stop_session(session_id: UUID, db: Database, session: CsrfProtected) -> dict[str, object]:
    try:
        changed = PaperTradingService(db).stop(session_id)
    except PaperSessionNotFound as exc:
        raise HTTPException(status_code=404) from exc
    AuditService(db).record(session.administrator_id, "PAPER_STOP", "paper_session", str(session_id), {"changed": changed})
    return {"stopped": changed}


@router.post("/emergency-stop/all")
def emergency_stop(db: Database, session: CsrfProtected) -> dict[str, int]:
    stopped = PaperTradingService(db).stop_all()
    AuditService(db).record(session.administrator_id, "PAPER_EMERGENCY_STOP", "paper_session", metadata={"stopped": stopped})
    return {"stopped": stopped}


@router.get("/audit/events")
def audit_events(db: Database, _admin: Authenticated, limit: Annotated[int, Query(ge=1, le=500)] = 100):
    return [{
        "id": str(item.id), "action": item.action, "subject_type": item.subject_type,
        "subject_id": item.subject_id, "metadata": item.event_metadata,
        "created_at": item.created_at.isoformat(),
    } for item in AuditService(db).list(limit)]
