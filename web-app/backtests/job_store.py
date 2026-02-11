from __future__ import annotations

import json
import os
import signal
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class JobPaths:
    job_dir: Path
    params_json: Path
    status_json: Path
    result_json: Path
    stdout_log: Path
    stderr_log: Path


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def jobs_root(base_dir: Path) -> Path:
    return base_dir / "var" / "jobs"


def ensure_job_dirs(base_dir: Path) -> None:
    jobs_root(base_dir).mkdir(parents=True, exist_ok=True)


def create_job(base_dir: Path, params: dict[str, Any]) -> tuple[str, JobPaths]:
    ensure_job_dirs(base_dir)
    job_id = str(uuid.uuid4())
    job_dir = jobs_root(base_dir) / job_id
    job_dir.mkdir(parents=True, exist_ok=False)

    paths = JobPaths(
        job_dir=job_dir,
        params_json=job_dir / "params.json",
        status_json=job_dir / "status.json",
        result_json=job_dir / "result.json",
        stdout_log=job_dir / "stdout.log",
        stderr_log=job_dir / "stderr.log",
    )

    paths.params_json.write_text(json.dumps(params, indent=2, default=str), encoding="utf-8")
    paths.status_json.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "status": "queued",
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "pid": None,
                "python_executable": None,
                "returncode": None,
                "error": None,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return job_id, paths


def read_status(paths: JobPaths) -> dict[str, Any]:
    if not paths.status_json.exists():
        return {"status": "unknown", "error": "Missing status.json"}
    return json.loads(paths.status_json.read_text(encoding="utf-8"))


def write_status(paths: JobPaths, patch: dict[str, Any]) -> None:
    status = read_status(paths)
    status.update(patch)
    status["updated_at"] = _now_iso()
    paths.status_json.write_text(json.dumps(status, indent=2), encoding="utf-8")


def is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def tail_text_file(path: Path, max_bytes: int = 32_000) -> str:
    if not path.exists():
        return ""
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            start = max(0, size - max_bytes)
            f.seek(start)
            data = f.read().decode("utf-8", errors="replace")
            return data
    except Exception as e:
        return f"[tail error] {e}"

