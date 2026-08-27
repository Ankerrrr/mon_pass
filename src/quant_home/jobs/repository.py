from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from quant_home.jobs.models import BackgroundJob
from quant_home.jobs.types import ACTIVE_JOB_STATUSES, JobStatus


class JobNotFound(Exception):
    pass


class InvalidJobTransition(Exception):
    pass


_ALLOWED_TRANSITIONS = {
    JobStatus.QUEUED: {*ACTIVE_JOB_STATUSES, JobStatus.CANCELLED, JobStatus.INTERRUPTED},
    **{
        active: {
            *ACTIVE_JOB_STATUSES,
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.INTERRUPTED,
        }
        for active in ACTIVE_JOB_STATUSES
    },
}


class JobRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def insert(
        self,
        *,
        status: JobStatus,
        kind: str,
        payload: dict[str, Any],
    ) -> UUID:
        with self.session_factory() as db:
            job = BackgroundJob(status=status, kind=kind, payload=payload)
            db.add(job)
            db.commit()
            return job.id

    def get(self, job_id: UUID) -> BackgroundJob:
        with self.session_factory() as db:
            job = db.get(BackgroundJob, job_id)
            if job is None:
                raise JobNotFound
            db.expunge(job)
            return job

    def latest(self) -> BackgroundJob:
        with self.session_factory() as db:
            job = db.scalar(
                select(BackgroundJob).order_by(BackgroundJob.created_at.desc()).limit(1)
            )
            if job is None:
                raise JobNotFound
            db.expunge(job)
            return job

    def list(self) -> list[BackgroundJob]:
        with self.session_factory() as db:
            jobs = list(
                db.scalars(
                    select(BackgroundJob).order_by(BackgroundJob.created_at.desc())
                )
            )
            for job in jobs:
                db.expunge(job)
            return jobs

    def transition(
        self,
        job_id: UUID,
        status: JobStatus,
        *,
        progress: float | None = None,
        error: str | None = None,
    ) -> None:
        with self.session_factory() as db:
            current = db.get(BackgroundJob, job_id)
            if current is None:
                raise JobNotFound
            allowed = _ALLOWED_TRANSITIONS.get(current.status, set())
            if status != current.status and status not in allowed:
                raise InvalidJobTransition(
                    f"cannot transition {current.status.value} to {status.value}"
                )
            values: dict[str, Any] = {"status": status, "error": error}
            if progress is not None:
                values["progress"] = max(0.0, min(1.0, progress))
            result = db.execute(
                update(BackgroundJob)
                .where(
                    BackgroundJob.id == job_id,
                    BackgroundJob.status == current.status,
                )
                .values(**values)
            )
            if result.rowcount == 0:
                raise InvalidJobTransition("job state changed concurrently")
            db.commit()

    def request_cancel(self, job_id: UUID) -> None:
        with self.session_factory() as db:
            result = db.execute(
                update(BackgroundJob)
                .where(
                    BackgroundJob.id == job_id,
                    BackgroundJob.status.in_({JobStatus.QUEUED, *ACTIVE_JOB_STATUSES}),
                )
                .values(cancel_requested=True)
            )
            if result.rowcount == 0:
                if db.get(BackgroundJob, job_id) is None:
                    raise JobNotFound
                raise InvalidJobTransition("terminal jobs cannot be cancelled")
            db.commit()

    def is_cancel_requested(self, job_id: UUID) -> bool:
        return self.get(job_id).cancel_requested

    def mark_interrupted_jobs(self) -> int:
        with self.session_factory() as db:
            result = db.execute(
                update(BackgroundJob)
                .where(
                    BackgroundJob.status.in_({JobStatus.QUEUED, *ACTIVE_JOB_STATUSES})
                )
                .values(status=JobStatus.INTERRUPTED)
            )
            db.commit()
            return result.rowcount
