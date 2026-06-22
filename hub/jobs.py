"""后台任务管理与 JobResult 序列化。"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
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
    progress: dict[str, Any] | None = None
    log_tail: list[str] = field(default_factory=list)


class JobManager:
    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="hub-job")
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        self._max_log_lines = 800

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

    def submit_builder(self, job_type: str, fn_builder: Callable[[str], Callable[[], JobResult]]) -> str:
        """提交任务；fn_builder 接收 job_id，返回实际执行函数（用于训练进度回调）。"""
        job_id = uuid.uuid4().hex[:12]
        record = JobRecord(
            id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            created_at=time(),
        )
        with self._lock:
            self._jobs[job_id] = record

        fn = fn_builder(job_id)

        def _run() -> None:
            with self._lock:
                record.status = JobStatus.RUNNING
            try:
                outcome = fn()
                with self._lock:
                    record.status = JobStatus.COMPLETED
                    record.result = job_result_to_dict(outcome)
                    if record.progress is None:
                        record.progress = {"status": "completed", "percent": 100.0}
                    else:
                        record.progress = {**record.progress, "status": "completed", "percent": 100.0}
            except Exception as exc:
                with self._lock:
                    record.status = JobStatus.FAILED
                    record.error = str(exc)
                    if record.progress is None:
                        record.progress = {"status": "failed"}
                    else:
                        record.progress = {**record.progress, "status": "failed"}

        self._executor.submit(_run)
        return job_id

    def update_live(
        self,
        job_id: str,
        *,
        progress: dict[str, Any] | None = None,
        log_line: str | None = None,
    ) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return
            if progress is not None:
                record.progress = progress
            if log_line:
                record.log_tail.append(log_line.rstrip("\n"))
                if len(record.log_tail) > self._max_log_lines:
                    record.log_tail = record.log_tail[-self._max_log_lines :]

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
            "progress": record.progress,
            "log_tail": record.log_tail[-150:],
        }


job_manager = JobManager()
