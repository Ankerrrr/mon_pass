from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from quant_home.api.auth import require_admin, require_csrf
from quant_home.auth.models import Administrator, AdminSession
from quant_home.audit.service import AuditService
from quant_home.backtest.config import (
    AllocationConfig,
    BacktestConfig,
    GridConfig,
    MeanReversionConfig,
    TrendConfig,
)
from quant_home.configurations.repository import (
    ConfigurationNameConflict,
    ConfigurationNotFound,
    ConfigurationRepository,
    ConfigurationSnapshot,
)
from quant_home.configurations.service import ConfigurationService
from quant_home.db import get_db


router = APIRouter(prefix="/configurations", tags=["configurations"])
Database = Annotated[Session, Depends(get_db)]
Authenticated = Annotated[Administrator, Depends(require_admin)]
CsrfProtected = Annotated[AdminSession, Depends(require_csrf)]


class ConfigurationWrite(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    payload: BacktestConfig


class CloneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def _repository(db: Session) -> ConfigurationRepository:
    return ConfigurationRepository(db)


def _json(item: ConfigurationSnapshot) -> dict[str, object]:
    return {
        "id": str(item.configuration.id),
        "name": item.version.name,
        "version": item.version.version,
        "description": item.version.description,
        "payload": item.version.payload,
        "created_at": item.version.created_at.isoformat(),
        "updated_at": item.configuration.updated_at.isoformat(),
    }


def _conflict(exc: ConfigurationNameConflict) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="name already exists")


@router.get("")
def list_configurations(
    db: Database, _administrator: Authenticated
) -> list[dict[str, object]]:
    return [_json(item) for item in _repository(db).list()]


@router.get("/defaults")
def configuration_defaults(_administrator: Authenticated) -> dict[str, object]:
    return {
        "initial_capital": "10000",
        "allocations": AllocationConfig().model_dump(mode="json"),
        "intervals": {"trend": "4h", "mean_reversion": "1h", "grid": "15m"},
        "trend": TrendConfig().model_dump(mode="json"),
        "mean_reversion": MeanReversionConfig().model_dump(mode="json"),
        "grid": GridConfig().model_dump(mode="json"),
        "fee_rate": "0.001",
        "slippage_bps": "5",
    }


@router.post("/import", status_code=status.HTTP_201_CREATED)
def import_configuration(
    payload: ConfigurationWrite,
    db: Database,
    _session: CsrfProtected,
) -> dict[str, object]:
    try:
        item = ConfigurationService(_repository(db)).create(
            payload.name.strip(),
            payload.description,
            payload.payload.model_dump(mode="json"),
        )
    except ConfigurationNameConflict as exc:
        raise _conflict(exc) from exc
    AuditService(db).record(_session.administrator_id, "CONFIGURATION_IMPORT", "configuration", str(item.configuration.id))
    return _json(item)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_configuration(
    payload: ConfigurationWrite,
    db: Database,
    _session: CsrfProtected,
) -> dict[str, object]:
    try:
        item = ConfigurationService(_repository(db)).create(
            payload.name.strip(),
            payload.description,
            payload.payload.model_dump(mode="json"),
        )
    except ConfigurationNameConflict as exc:
        raise _conflict(exc) from exc
    AuditService(db).record(_session.administrator_id, "CONFIGURATION_CREATE", "configuration", str(item.configuration.id))
    return _json(item)


@router.get("/{configuration_id}")
def configuration_detail(
    configuration_id: UUID,
    db: Database,
    _administrator: Authenticated,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, object]:
    try:
        return _json(_repository(db).get(configuration_id, version))
    except ConfigurationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


@router.put("/{configuration_id}")
def update_configuration(
    configuration_id: UUID,
    payload: ConfigurationWrite,
    db: Database,
    _session: CsrfProtected,
) -> dict[str, object]:
    try:
        item = ConfigurationService(_repository(db)).update(
            configuration_id,
            payload.name.strip(),
            payload.description,
            payload.payload.model_dump(mode="json"),
        )
    except ConfigurationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except ConfigurationNameConflict as exc:
        raise _conflict(exc) from exc
    AuditService(db).record(_session.administrator_id, "CONFIGURATION_UPDATE", "configuration", str(configuration_id), {"version": item.version.version})
    return _json(item)


@router.post("/{configuration_id}/clone", status_code=status.HTTP_201_CREATED)
def clone_configuration(
    configuration_id: UUID,
    payload: CloneRequest,
    db: Database,
    _session: CsrfProtected,
) -> dict[str, object]:
    try:
        item = ConfigurationService(_repository(db)).clone(
            configuration_id, payload.name.strip()
        )
    except ConfigurationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except ConfigurationNameConflict as exc:
        raise _conflict(exc) from exc
    AuditService(db).record(_session.administrator_id, "CONFIGURATION_CLONE", "configuration", str(item.configuration.id), {"source_id": str(configuration_id)})
    return _json(item)


@router.get("/{configuration_id}/export")
def export_configuration(
    configuration_id: UUID,
    db: Database,
    _administrator: Authenticated,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> dict[str, object]:
    try:
        item = _repository(db).get(configuration_id, version)
    except ConfigurationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return {
        "name": item.version.name,
        "description": item.version.description,
        "payload": item.version.payload,
        "version": item.version.version,
    }


@router.delete("/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_configuration(
    configuration_id: UUID,
    db: Database,
    _session: CsrfProtected,
) -> None:
    try:
        _repository(db).delete(configuration_id)
    except ConfigurationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    AuditService(db).record(_session.administrator_id, "CONFIGURATION_DELETE", "configuration", str(configuration_id))
