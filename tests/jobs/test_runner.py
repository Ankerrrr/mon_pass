import asyncio
from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine

from quant_home.db import Base, create_session_factory
from quant_home.jobs.repository import InvalidJobTransition, JobRepository
from quant_home.jobs.runner import JobExecutionContext, JobRunner
from quant_home.jobs.types import JobStatus


@dataclass
class ConcurrencyTracker:
    active: int = 0
    maximum_active: int = 0


class TrackingJobSpec:
    kind = "test"

    def __init__(self, index: int, tracker: ConcurrencyTracker) -> None:
        self.index = index
        self.tracker = tracker

    def snapshot(self):
        return {"index": self.index}

    async def run(self, context: JobExecutionContext) -> None:
        await context.checkpoint()
        self.tracker.active += 1
        self.tracker.maximum_active = max(
            self.tracker.maximum_active, self.tracker.active
        )
        await asyncio.sleep(0.01)
        self.tracker.active -= 1


def repository() -> JobRepository:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return JobRepository(create_session_factory(engine))


def test_runner_never_exceeds_configured_concurrency():
    async def scenario():
        tracker = ConcurrencyTracker()
        runner = JobRunner(repository(), max_concurrency=3)
        for index in range(20):
            await runner.submit(TrackingJobSpec(index, tracker))
        await runner.drain()
        assert tracker.maximum_active == 3

    asyncio.run(scenario())


def test_startup_marks_running_jobs_interrupted():
    jobs = repository()
    jobs.insert(status=JobStatus.RUNNING, kind="test", payload={})

    assert jobs.mark_interrupted_jobs() == 1
    assert jobs.latest().status is JobStatus.INTERRUPTED


def test_startup_marks_unrecoverable_queued_jobs_interrupted():
    jobs = repository()
    jobs.insert(status=JobStatus.QUEUED, kind="test", payload={})

    assert jobs.mark_interrupted_jobs() == 1
    assert jobs.latest().status is JobStatus.INTERRUPTED


def test_terminal_job_cannot_be_cancelled():
    jobs = repository()
    job_id = jobs.insert(status=JobStatus.COMPLETED, kind="test", payload={})

    with pytest.raises(InvalidJobTransition):
        jobs.request_cancel(job_id)


def test_cancellation_preserves_completed_atomic_units():
    async def scenario():
        completed: list[int] = []
        first_completed = asyncio.Event()
        continue_work = asyncio.Event()

        class AtomicJobSpec:
            kind = "atomic-test"

            def snapshot(self):
                return {"units": 3}

            async def run(self, context):
                for unit in range(3):
                    await context.checkpoint()
                    completed.append(unit)
                    if unit == 0:
                        first_completed.set()
                        await continue_work.wait()

        jobs = repository()
        runner = JobRunner(jobs, max_concurrency=1)
        job_id = await runner.submit(AtomicJobSpec())
        await first_completed.wait()
        runner.cancel(job_id)
        continue_work.set()
        await runner.drain()

        assert completed == [0]
        assert jobs.get(job_id).status is JobStatus.CANCELLED

    asyncio.run(scenario())
