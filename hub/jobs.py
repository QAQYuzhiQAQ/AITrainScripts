"""后台任务管理与 JobResult 序列化。"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from time import time
from typing import Any, Callable

from img_tools.common import JobResult


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def job_result_to_dict(result: JobResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "message": result.message,
        "processed": result.processed,
        "skipped": result.skipped,
        "errors": list(result.errors),
        "details": list(result.details),
        "outputs": [str(p) for p in result.outputs],
    }


@dataclass
class JobRecord:
    id: str
    job_type: str
    status: JobStatus
    created_at: float
    result: dict[str, Any] | None = None
    error: str | None = None


class JobManager:
    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="hub-job")
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def submit(self, job_type: str, fn: Callable[[], JobResult]) -> str:
        job_id = uuid.uuid4().hex[:12]
        record = JobRecord(
            id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            created_at=time(),
        )
        with self._lock:
            self._jobs[job_id] = record

        def _run() -> None:
            with self._lock:
                record.status = JobStatus.RUNNING
            try:
                outcome = fn()
                with self._lock:
                    record.status = JobStatus.COMPLETED
                    record.result = job_result_to_dict(outcome)
            except Exception as exc:
                with self._lock:
                    record.status = JobStatus.FAILED
                    record.error = str(exc)

        self._executor.submit(_run)
        return job_id

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def to_dict(self, record: JobRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "type": record.job_type,
            "status": record.status.value,
            "created_at": record.created_at,
            "result": record.result,
            "error": record.error,
        }


job_manager = JobManager()
