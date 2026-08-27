from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from quant_home.api.auth import require_admin, require_csrf
from quant_home.auth.models import Administrator, AdminSession
from quant_home.db import get_db
from quant_home.market.candles import CandleInterval
from quant_home.market.models import CandleDataset
from quant_home.market.repository import CandleRepository, DatasetInUse, DatasetNotFound


router = APIRouter(prefix="/datasets", tags=["datasets"])
Database = Annotated[Session, Depends(get_db)]
Authenticated = Annotated[Administrator, Depends(require_admin)]
CsrfProtected = Annotated[AdminSession, Depends(require_csrf)]


class RefreshDatasetRequest(BaseModel):
    symbol: str = Field(pattern=r"^[A-Za-z0-9]{2,32}$")
    interval: CandleInterval
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def timestamps_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def start_must_precede_end(self):
        if self.start >= self.end:
            raise ValueError("start must precede end")
        interval_microseconds = int(self.interval.duration.total_seconds() * 1_000_000)
        if (
            int(self.start.timestamp() * 1_000_000) % interval_microseconds
            or int(self.end.timestamp() * 1_000_000) % interval_microseconds
        ):
            raise ValueError("range must align to candle interval boundaries")
        return self


def _repository(request: Request, db: Session) -> CandleRepository:
    return CandleRepository(db, request.app.state.candle_downloader)


def _dataset_json(dataset: CandleDataset) -> dict[str, object]:
    return {
        "id": str(dataset.id),
        "symbol": dataset.symbol,
        "interval": dataset.interval,
        "start": dataset.start_time.isoformat(),
        "end": dataset.end_time.isoformat(),
        "fingerprint": dataset.fingerprint,
        "candle_count": dataset.candle_count,
        "is_valid": dataset.is_valid,
        "reference_count": dataset.reference_count,
    }


@router.get("")
def list_datasets(
    request: Request,
    db: Database,
    _administrator: Authenticated,
) -> list[dict[str, object]]:
    return [_dataset_json(item) for item in _repository(request, db).list()]


@router.get("/{dataset_id}")
def dataset_detail(
    dataset_id: UUID,
    request: Request,
    db: Database,
    _administrator: Authenticated,
) -> dict[str, object]:
    try:
        return _dataset_json(_repository(request, db).get(dataset_id))
    except DatasetNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


@router.get("/{dataset_id}/issues")
def dataset_issues(
    dataset_id: UUID,
    request: Request,
    db: Database,
    _administrator: Authenticated,
) -> list[dict[str, str | None]]:
    try:
        dataset = _repository(request, db).get(dataset_id)
    except DatasetNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return [
        {"code": issue.code, "message": issue.message, "open_time": issue.open_time}
        for issue in dataset.issues
    ]


@router.post("/refresh", status_code=status.HTTP_201_CREATED)
def refresh_dataset(
    payload: RefreshDatasetRequest,
    request: Request,
    db: Database,
    _session: CsrfProtected,
) -> dict[str, object]:
    dataset = _repository(request, db).ensure_range(
        payload.symbol,
        payload.interval,
        payload.start,
        payload.end,
    )
    return _dataset_json(dataset)


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: UUID,
    request: Request,
    db: Database,
    _session: CsrfProtected,
) -> None:
    try:
        _repository(request, db).delete_unused(dataset_id)
    except DatasetNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except DatasetInUse as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dataset is referenced and cannot be deleted",
        ) from exc
