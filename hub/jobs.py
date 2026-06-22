"""后台任务管理与 JobResult 序列化。"""

from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from time import time
from typing import Any, Callable

from img_tools.common import JobResult

HISTORY_FILE = Path(__file__).resolve().parent / ".job_history.json"
MAX_HISTORY = 200


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
    progress_message: str | None = None
    progress_lines: list[str] = field(default_factory=list)
    label: str | None = None
    batch_id: str | None = None


class JobManager:
    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="hub-job")
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        self._load_history()

    def submit(
        self,
        job_type: str,
        fn: Callable[..., JobResult],
        *,
        with_progress: bool = False,
        label: str | None = None,
        batch_id: str | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        record = JobRecord(
            id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            created_at=time(),
            label=label,
            batch_id=batch_id,
        )
        with self._lock:
            self._jobs[job_id] = record
        self._persist_history()

        def _report(message: str) -> None:
            self.report_progress(job_id, message)

        def _run() -> None:
            with self._lock:
                record.status = JobStatus.RUNNING
            self.report_progress(job_id, "后台任务已启动")
            try:
                outcome = fn(_report) if with_progress else fn()
                with self._lock:
                    record.status = JobStatus.COMPLETED
                    record.result = job_result_to_dict(outcome)
            except Exception as exc:
                with self._lock:
                    record.status = JobStatus.FAILED
                    record.error = str(exc)
            self._persist_history()

        self._executor.submit(_run)
        return job_id

    def report_progress(self, job_id: str, message: str) -> None:
        from datetime import datetime

        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {message}"
        with self._lock:
            record = self._jobs.get(job_id)
            if not record:
                return
            record.progress_message = message
            record.progress_lines.append(line)

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(
        self,
        *,
        job_type: str | None = None,
        batch_id: str | None = None,
        limit: int = 50,
    ) -> list[JobRecord]:
        with self._lock:
            records = list(self._jobs.values())
        records.sort(key=lambda r: r.created_at, reverse=True)
        if job_type:
            records = [r for r in records if r.job_type == job_type]
        if batch_id:
            records = [r for r in records if r.batch_id == batch_id]
        return records[:limit]

    def to_dict(self, record: JobRecord) -> dict[str, Any]:
        return {
            "id": record.id,
            "type": record.job_type,
            "status": record.status.value,
            "created_at": record.created_at,
            "label": record.label,
            "batch_id": record.batch_id,
            "result": record.result,
            "error": record.error,
            "progress_message": record.progress_message,
            "progress_lines": list(record.progress_lines),
        }

    def _persist_history(self) -> None:
        with self._lock:
            records = sorted(self._jobs.values(), key=lambda r: r.created_at, reverse=True)[:MAX_HISTORY]
            payload = [self.to_dict(r) for r in records]
        try:
            HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            HISTORY_FILE.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    def _load_history(self) -> None:
        if not HISTORY_FILE.is_file():
            return
        try:
            payload = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(payload, list):
            return
        for item in payload:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            try:
                status = JobStatus(str(item.get("status", "completed")))
            except ValueError:
                status = JobStatus.COMPLETED
            record = JobRecord(
                id=str(item["id"]),
                job_type=str(item.get("type", "unknown")),
                status=status,
                created_at=float(item.get("created_at", 0)),
                result=item.get("result"),
                error=item.get("error"),
                progress_message=item.get("progress_message"),
                progress_lines=list(item.get("progress_lines") or []),
                label=item.get("label"),
                batch_id=item.get("batch_id"),
            )
            self._jobs[record.id] = record


job_manager = JobManager()
