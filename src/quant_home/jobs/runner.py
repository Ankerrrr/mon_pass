import asyncio
from typing import Any, Protocol
from uuid import UUID

from quant_home.jobs.repository import JobRepository
from quant_home.jobs.types import JobStatus


class JobCancelled(Exception):
    pass


class JobSpec(Protocol):
    kind: str

    def snapshot(self) -> dict[str, Any]: ...

    async def run(self, context: "JobExecutionContext") -> None: ...


class JobExecutionContext:
    def __init__(self, job_id: UUID, repository: JobRepository) -> None:
        self.job_id = job_id
        self.repository = repository

    async def checkpoint(self) -> None:
        if self.repository.is_cancel_requested(self.job_id):
            raise JobCancelled
        await asyncio.sleep(0)

    def stage(self, status: JobStatus, progress: float | None = None) -> None:
        if status not in {
            JobStatus.DOWNLOADING,
            JobStatus.VALIDATING,
            JobStatus.RUNNING,
            JobStatus.AGGREGATING,
        }:
            raise ValueError("Execution context accepts active stages only")
        self.repository.transition(self.job_id, status, progress=progress)

    def set_progress(self, progress: float) -> None:
        current = self.repository.get(self.job_id)
        self.repository.transition(self.job_id, current.status, progress=progress)


class JobRunner:
    def __init__(self, repository: JobRepository, max_concurrency: int = 3) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        self.repository = repository
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tasks: dict[UUID, asyncio.Task[None]] = {}

    async def submit(self, spec: JobSpec) -> UUID:
        job_id = self.repository.insert(
            status=JobStatus.QUEUED,
            kind=spec.kind,
            payload=spec.snapshot(),
        )
        task = asyncio.create_task(self._execute(job_id, spec))
        self._tasks[job_id] = task
        return job_id

    def cancel(self, job_id: UUID) -> None:
        self.repository.request_cancel(job_id)

    async def drain(self) -> None:
        tasks = list(self._tasks.values())
        if tasks:
            await asyncio.gather(*tasks)

    async def _execute(self, job_id: UUID, spec: JobSpec) -> None:
        try:
            async with self._semaphore:
                context = JobExecutionContext(job_id, self.repository)
                await context.checkpoint()
                self.repository.transition(job_id, JobStatus.RUNNING)
                await spec.run(context)
                await context.checkpoint()
                self.repository.transition(job_id, JobStatus.COMPLETED, progress=1.0)
        except JobCancelled:
            self.repository.transition(job_id, JobStatus.CANCELLED)
        except Exception as exc:
            self.repository.transition(job_id, JobStatus.FAILED, error=str(exc))
        finally:
            self._tasks.pop(job_id, None)
