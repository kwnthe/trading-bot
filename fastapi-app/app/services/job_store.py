import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import uuid

from app.core.config import settings


class JobPaths:
    def __init__(self, job_dir: Path):
        self.job_dir = job_dir
        self.params_json = job_dir / "params.json"
        self.status_json = job_dir / "status.json"
        self.result_json = job_dir / "result.json"
        self.stdout_log = job_dir / "stdout.log"
        self.stderr_log = job_dir / "stderr.log"


def create_job(base_dir: Path, params: Dict[str, Any]) -> Tuple[str, JobPaths]:
    """Create a new job directory and return job_id and paths"""
    job_id = str(uuid.uuid4())
    job_dir = base_dir / "var" / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    paths = JobPaths(job_dir)
    
    # Save parameters
    with open(paths.params_json, 'w') as f:
        json.dump(params, f, indent=2, default=str)
    
    # Initialize status
    initial_status = {
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    with open(paths.status_json, 'w') as f:
        json.dump(initial_status, f, indent=2, default=str)
    
    return job_id, paths


def read_status(paths: JobPaths) -> Dict[str, Any]:
    """Read job status from status.json file"""
    try:
        if paths.status_json.exists():
            with open(paths.status_json, 'r') as f:
                return json.load(f)
        else:
            return {"status": "unknown", "error": "Status file not found"}
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return {"status": "unknown", "error": f"Failed to read status.json: {str(e)}"}


def write_status(paths: JobPaths, status_update: Dict[str, Any]) -> None:
    """Update job status"""
    current_status = read_status(paths)
    current_status.update(status_update)
    current_status["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    with open(paths.status_json, 'w') as f:
        json.dump(current_status, f, indent=2, default=str)


def is_pid_running(pid: int) -> bool:
    """Check if a process with given PID is running"""
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                  capture_output=True, text=True)
            return str(pid) in result.stdout
        else:  # Unix-like
            os.kill(pid, 0)
            return True
    except (OSError, subprocess.SubprocessError):
        return False


def tail_text_file(file_path: Path, num_lines: int = 20) -> str:
    """Get last N lines from a text file"""
    try:
        if not file_path.exists():
            return ""
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
            return ''.join(lines[-num_lines:])
    except Exception:
        return ""


def start_runner_process(base_dir: Path, paths: JobPaths) -> None:
    """Start the backtest runner process"""
    # Get the runner script path - check both FastAPI and original locations
    possible_paths = [
        base_dir.parent / "web-app" / "backtests" / "runner" / "run_backtest.py",
        base_dir.parent / "web-app" / "backtests" / "runner" / "run_live.py",
        base_dir / "web-app" / "backtests" / "runner" / "run_backtest.py",
        base_dir / "web-app" / "backtests" / "runner" / "run_live.py",
    ]
    
    runner_script = None
    for path in possible_paths:
        if path.exists():
            runner_script = path
            break
    
    if runner_script is None:
        raise FileNotFoundError(f"Runner script not found. Checked: {possible_paths}")
    
    # Prepare environment
    env = os.environ.copy()
    # Add both the FastAPI app directory and the parent directory to Python path
    env['PYTHONPATH'] = f"{str(base_dir.parent)};{str(base_dir)}"
    
    # Start the process
    with open(paths.stdout_log, 'w') as stdout_file, \
         open(paths.stderr_log, 'w') as stderr_file:
        
        process = subprocess.Popen(
            [sys.executable, str(runner_script), "--job-dir", str(paths.job_dir)],
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
            cwd=str(base_dir)
        )
    
    # Update status with PID
    write_status(paths, {
        "status": "running",
        "pid": process.pid,
        "python_executable": sys.executable
    })


def get_job_paths(job_id: str) -> JobPaths:
    """Get JobPaths for a given job_id"""
    job_dir = settings.JOBS_DIR / job_id
    if not job_dir.exists():
        raise FileNotFoundError(f"Job {job_id} not found")
    return JobPaths(job_dir)


def cleanup_old_jobs(max_age_hours: int = 24) -> int:
    """Clean up old job directories"""
    cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
    cleaned_count = 0
    
    for job_dir in settings.JOBS_DIR.iterdir():
        if job_dir.is_dir():
            try:
                # Check modification time
                if job_dir.stat().st_mtime < cutoff_time:
                    # Remove directory and all contents
                    import shutil
                    shutil.rmtree(job_dir)
                    cleaned_count += 1
            except Exception as e:
                print(f"Failed to clean up job {job_dir.name}: {e}")
    
    return cleaned_count
