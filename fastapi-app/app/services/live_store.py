import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import uuid

from app.core.config import settings


class LivePaths:
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.params_json = session_dir / "params.json"
        self.status_json = session_dir / "status.json"
        self.snapshot_json = session_dir / "snapshot.json"
        self.stdout_log = session_dir / "stdout.log"
        self.stderr_log = session_dir / "stderr.log"


def create_live_session(base_dir: Path, params: Dict[str, Any]) -> Tuple[str, LivePaths]:
    """Create a new live session directory and return session_id and paths"""
    session_id = str(uuid.uuid4())
    session_dir = base_dir / "var" / "live" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    
    paths = LivePaths(session_dir)
    
    # Save parameters
    with open(paths.params_json, 'w') as f:
        json.dump(params, f, indent=2, default=str)
    
    # Initialize status
    initial_status = {
        "state": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    with open(paths.status_json, 'w') as f:
        json.dump(initial_status, f, indent=2, default=str)
    
    return session_id, paths


def read_live_status(paths: LivePaths) -> Dict[str, Any]:
    """Read live session status from status.json file"""
    try:
        if paths.status_json.exists():
            with open(paths.status_json, 'r') as f:
                return json.load(f)
        else:
            return {"state": "unknown", "error": "Status file not found"}
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return {"state": "unknown", "error": f"Failed to read status.json: {str(e)}"}


def write_live_status(paths: LivePaths, status_update: Dict[str, Any]) -> None:
    """Update live session status"""
    current_status = read_live_status(paths)
    current_status.update(status_update)
    current_status["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    with open(paths.status_json, 'w') as f:
        json.dump(current_status, f, indent=2, default=str)


def get_active_session_id(base_dir: Path) -> Optional[str]:
    """Get the currently active session ID"""
    active_file = base_dir / "var" / "live" / "active_session.txt"
    try:
        if active_file.exists():
            with open(active_file, 'r') as f:
                session_id = f.read().strip()
                return session_id if session_id else None
    except Exception:
        pass
    return None


def set_active_session_id(base_dir: Path, session_id: Optional[str]) -> None:
    """Set the active session ID"""
    active_file = base_dir / "var" / "live" / "active_session.txt"
    active_file.parent.mkdir(parents=True, exist_ok=True)
    
    if session_id:
        with open(active_file, 'w') as f:
            f.write(session_id)
    elif active_file.exists():
        active_file.unlink()


def tail_live_text_file(file_path: Path, num_lines: int = 20) -> str:
    """Get last N lines from a live session log file"""
    try:
        if not file_path.exists():
            return ""
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
            return ''.join(lines[-num_lines:])
    except Exception:
        return ""


def stop_session_pid(pid: Optional[int]) -> bool:
    """Stop a live session by PID"""
    if pid is None:
        return False
    
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['taskkill', '/PID', str(pid), '/F'], 
                                  capture_output=True)
            return result.returncode == 0
        else:  # Unix-like
            os.kill(pid, 15)  # SIGTERM
            return True
    except (OSError, subprocess.SubprocessError):
        return False


def start_live_runner_process(base_dir: Path, session_dir: Path, 
                            stdout_log: Path, stderr_log: Path) -> int:
    """Start the live trading runner process"""
    # Get the runner script path - check both FastAPI and original locations
    possible_paths = [
        base_dir.parent / "web-app" / "backtests" / "runner" / "run_live.py",
        base_dir / "web-app" / "backtests" / "runner" / "run_live.py",
    ]
    
    runner_script = None
    for path in possible_paths:
        if path.exists():
            runner_script = path
            break
    
    if runner_script is None:
        raise FileNotFoundError(f"Live runner script not found. Checked: {possible_paths}")
    
    # Prepare environment
    env = os.environ.copy()
    # Add both the FastAPI app directory and the parent directory to Python path
    env['PYTHONPATH'] = f"{str(base_dir.parent)};{str(base_dir)}"
    env['SESSION_DIR'] = str(session_dir)
    
    # Start the process
    with open(stdout_log, 'w') as stdout_file, \
         open(stderr_log, 'w') as stderr_file:
        
        process = subprocess.Popen(
            [sys.executable, str(runner_script), "--session-dir", str(session_dir)],
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
            cwd=str(base_dir)
        )
    
    return process.pid


def get_live_paths(session_id: str) -> LivePaths:
    """Get LivePaths for a given session_id"""
    session_dir = settings.LIVE_DIR / session_id
    if not session_dir.exists():
        raise FileNotFoundError(f"Live session {session_id} not found")
    return LivePaths(session_dir)


def cleanup_old_sessions(max_age_hours: int = 24) -> int:
    """Clean up old live session directories"""
    cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
    cleaned_count = 0
    
    for session_dir in settings.LIVE_DIR.iterdir():
        if session_dir.is_dir():
            try:
                # Check modification time
                if session_dir.stat().st_mtime < cutoff_time:
                    # Remove directory and all contents
                    import shutil
                    shutil.rmtree(session_dir)
                    cleaned_count += 1
            except Exception as e:
                print(f"Failed to clean up session {session_dir.name}: {e}")
    
    return cleaned_count
