from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .job_store import JobPaths, write_status


def repo_root_from_webapp(base_dir: Path) -> Path:
    # base_dir is .../web-app
    return base_dir.parent


def start_runner_process(base_dir: Path, paths: JobPaths) -> int:
    """
    Launch the backtest runner in a separate process so env var overrides
    are isolated per run (no cross-request leakage).
    """
    runner = base_dir / "backtests" / "runner" / "run_backtest.py"
    repo_root = repo_root_from_webapp(base_dir)

    env = os.environ.copy()
    # Ensure runner can import repo modules, and that pydantic config reads repo .env
    env["PYTHONPATH"] = str(repo_root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    stdout_f = paths.stdout_log.open("ab", buffering=0)
    stderr_f = paths.stderr_log.open("ab", buffering=0)

    # Allow forcing runner python (e.g. your main trading-bot venv)
    # Example: export BACKTEST_RUNNER_PYTHON="/path/to/venv/bin/python"
    runner_python = os.environ.get("BACKTEST_RUNNER_PYTHON") or sys.executable

    popen_kwargs: dict[str, object] = {}
    if os.name == "nt":
        # Detach child process from the dev-server console so Ctrl+C / reload
        # doesn't propagate KeyboardInterrupt into the runner.
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    p = subprocess.Popen(
        [runner_python, str(runner), "--job-dir", str(paths.job_dir)],
        cwd=str(repo_root),  # important: makes src/utils/config.py read repo ".env"
        env=env,
        stdout=stdout_f,
        stderr=stderr_f,
        **popen_kwargs,
    )

    write_status(paths, {"status": "running", "pid": p.pid, "python_executable": runner_python})
    return p.pid


def start_live_runner_process(base_dir: Path, session_dir: Path, stdout_log: Path, stderr_log: Path) -> int:
    runner = base_dir / "backtests" / "runner" / "run_live.py"
    repo_root = repo_root_from_webapp(base_dir)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    stdout_f = stdout_log.open("ab", buffering=0)
    stderr_f = stderr_log.open("ab", buffering=0)

    runner_python = os.environ.get("BACKTEST_RUNNER_PYTHON") or sys.executable

    popen_kwargs: dict[str, object] = {}
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    p = subprocess.Popen(
        [runner_python, str(runner), "--session-dir", str(session_dir)],
        cwd=str(repo_root),
        env=env,
        stdout=stdout_f,
        stderr=stderr_f,
        **popen_kwargs,
    )

    return p.pid

