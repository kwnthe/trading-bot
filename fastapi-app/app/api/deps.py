from fastapi import HTTPException, status
from typing import Dict, Any
from pathlib import Path

from app.core.config import settings
from app.services.job_store import get_job_paths, read_status, is_pid_running
from app.services.live_store import get_live_paths, read_live_status, get_active_session_id


def get_base_dir() -> Path:
    """Get the base directory for the application"""
    return settings.BASE_DIR


def validate_job_exists(job_id: str) -> Dict[str, Any]:
    """Validate that a job exists and return its paths"""
    try:
        paths = get_job_paths(job_id)
        status_data = read_status(paths)
        return {"paths": paths, "status": status_data}
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )


def validate_live_session_exists(session_id: str) -> Dict[str, Any]:
    """Validate that a live session exists and return its paths"""
    try:
        paths = get_live_paths(session_id)
        status_data = read_live_status(paths)
        return {"paths": paths, "status": status_data}
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live session {session_id} not found"
        )


def check_no_active_live_session() -> None:
    """Check that there's no currently active live session"""
    active = get_active_session_id(settings.BASE_DIR)
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A live session is already running: {active}"
        )


def validate_session_not_running(session_id: str) -> None:
    """Validate that a session is not currently running"""
    try:
        paths = get_live_paths(session_id)
        status_data = read_live_status(paths)
        
        state = status_data.get("state")
        if state in {"queued", "running"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Live session {session_id} is already {state}"
            )
    except FileNotFoundError:
        # Session doesn't exist, which is fine for this validation
        pass


def update_job_status_if_died(paths, status_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update job status if the process died"""
    from app.services.job_store import write_status
    
    pid = status_data.get("pid")
    if status_data.get("status") == "running" and pid and not is_pid_running(int(pid)):
        # Runner died without updating status
        if not paths.result_json.exists():
            write_status(paths, {
                "status": "failed", 
                "returncode": status_data.get("returncode"), 
                "error": "Runner process ended"
            })
        return read_status(paths)
    return status_data


def update_live_status_if_died(paths, status_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update live session status if the process died"""
    from app.services.live_store import write_live_status, set_active_session_id
    
    pid = status_data.get("pid")
    state = status_data.get("state")
    
    if pid and not is_pid_running(int(pid)) and state in {"queued", "running", "error"}:
        write_live_status(paths, {
            "state": "stopped", 
            "returncode": status_data.get("returncode"), 
            "error": status_data.get("error")
        })
        
        # Clear active marker if this was the active session
        if get_active_session_id(settings.BASE_DIR) == paths.session_dir.name:
            set_active_session_id(settings.BASE_DIR, None)
        
        return read_live_status(paths)
    
    # Clear active marker if session is no longer running
    if state in {"stopped", "error"} and get_active_session_id(settings.BASE_DIR) == paths.session_dir.name:
        set_active_session_id(settings.BASE_DIR, None)
    
    return status_data
