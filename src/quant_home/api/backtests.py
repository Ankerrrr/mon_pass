from __future__ import annotations

import csv
from io import StringIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from quant_home.api.auth import require_admin, require_csrf
from quant_home.auth.models import Administrator, AdminSession
from quant_home.audit.service import AuditService
from quant_home.backtest.models import BacktestRun
from quant_home.backtest.analysis import enrich_snapshot
from quant_home.backtest.repository import BacktestRepository, BacktestRunNotFound
from quant_home.backtest.service import BacktestService, DuplicateBacktest
from quant_home.configurations.repository import ConfigurationNotFound
from quant_home.db import get_db


router = APIRouter(prefix="/backtests", tags=["backtests"])
Database = Annotated[Session, Depends(get_db)]
Authenticated = Annotated[Administrator, Depends(require_admin)]
CsrfProtected = Annotated[AdminSession, Depends(require_csrf)]


class CreateBacktestRequest(BaseModel):
    configuration_id: UUID
    configuration_version: int | None = Field(default=None, ge=1)
    confirm_duplicate: bool = False


def _repository(request: Request) -> BacktestRepository:
    return BacktestRepository(request.app.state.session_factory)


def _run_json(run: BacktestRun) -> dict[str, object]:
    return {
        "id": str(run.id),
        "job_id": str(run.job_id) if run.job_id else None,
        "configuration_snapshot": run.configuration_snapshot,
        "dataset_fingerprints": run.dataset_fingerprints,
        "result_snapshot": enrich_snapshot(run.result_snapshot),
        "engine_version": run.engine_version,
        "fingerprint": run.fingerprint,
        "created_at": run.created_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_backtest(
    payload: CreateBacktestRequest,
    request: Request,
    db: Database,
    _session: CsrfProtected,
) -> dict[str, str]:
    service = BacktestService(
        db,
        request.app.state.session_factory,
        request.app.state.candle_downloader,
        request.app.state.job_runner,
    )
    try:
        job_id = await service.create_run(
            payload.configuration_id,
            version=payload.configuration_version,
            confirm_duplicate=payload.confirm_duplicate,
        )
    except ConfigurationNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    except DuplicateBacktest as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An identical backtest was already submitted; confirm duplicate to rerun",
        ) from exc
    return {"job_id": str(job_id)}


@router.get("")
def list_backtests(
    request: Request,
    _administrator: Authenticated,
) -> list[dict[str, object]]:
    return [_run_json(run) for run in _repository(request).list()]


@router.get("/jobs/{job_id}")
def backtest_by_job(
    job_id: UUID,
    request: Request,
    _administrator: Authenticated,
) -> dict[str, object]:
    try:
        return _run_json(_repository(request).get_by_job(job_id))
    except BacktestRunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


@router.get("/{run_id}/trades.csv")
def export_backtest_trades(
    run_id: UUID,
    request: Request,
    _administrator: Authenticated,
) -> Response:
    try:
        run = _repository(request).get(run_id)
    except BacktestRunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc

    output = StringIO(newline="")
    columns = ("strategy", "symbol", "side", "quantity", "price", "fee")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\r\n")
    writer.writeheader()
    for strategy, ledger in sorted(run.result_snapshot["ledgers"].items()):
        for fill in ledger["fills"]:
            writer.writerow(
                {
                    "strategy": strategy,
                    "symbol": fill["symbol"],
                    "side": fill["side"],
                    "quantity": fill["quantity"],
                    "price": fill["price"],
                    "fee": fill["fee"],
                }
            )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="backtest-{run_id}-trades.csv"'
        },
    )


@router.get("/{run_id}")
def backtest_detail(
    run_id: UUID,
    request: Request,
    _administrator: Authenticated,
) -> dict[str, object]:
    try:
        return _run_json(_repository(request).get(run_id))
    except BacktestRunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_backtest(
    run_id: UUID, request: Request, db: Database, session: CsrfProtected
) -> None:
    try:
        _repository(request).delete(run_id)
    except BacktestRunNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    AuditService(db).record(session.administrator_id, "BACKTEST_DELETE", "backtest", str(run_id))
