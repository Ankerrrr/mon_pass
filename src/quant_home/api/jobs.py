from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from quant_home.api.auth import require_admin, require_csrf
from quant_home.auth.models import Administrator, AdminSession
from quant_home.jobs.models import BackgroundJob
from quant_home.jobs.repository import JobNotFound


router = APIRouter(prefix="/jobs", tags=["jobs"])
Authenticated = Annotated[Administrator, Depends(require_admin)]
CsrfProtected = Annotated[AdminSession, Depends(require_csrf)]


def _job_json(job: BackgroundJob) -> dict[str, object]:
    return {
        "id": str(job.id),
        "kind": job.kind,
        "payload": job.payload,
        "status": job.status.value,
        "progress": job.progress,
        "cancel_requested": job.cancel_requested,
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


@router.get("")
def list_jobs(
    request: Request,
    _administrator: Authenticated,
) -> list[dict[str, object]]:
    return [_job_json(job) for job in request.app.state.job_repository.list()]


@router.get("/{job_id}")
def job_detail(
    job_id: UUID,
    request: Request,
    _administrator: Authenticated,
) -> dict[str, object]:
    try:
        return _job_json(request.app.state.job_repository.get(job_id))
    except JobNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc


@router.post("/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
def cancel_job(
    job_id: UUID,
    request: Request,
    _session: CsrfProtected,
) -> dict[str, str]:
    try:
        request.app.state.job_runner.cancel(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
    return {"status": "cancellation_requested"}
