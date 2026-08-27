from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    VALIDATING = "validating"
    RUNNING = "running"
    AGGREGATING = "aggregating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


ACTIVE_JOB_STATUSES = {
    JobStatus.DOWNLOADING,
    JobStatus.VALIDATING,
    JobStatus.RUNNING,
    JobStatus.AGGREGATING,
}

TERMINAL_JOB_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
    JobStatus.INTERRUPTED,
}
