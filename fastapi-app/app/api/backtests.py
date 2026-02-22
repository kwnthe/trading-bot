import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import JSONResponse

from app.models.schemas import (
    BacktestRequest, LiveTradingRequest, JobStatus, LiveSessionStatus,
    LiveSessionStart, LiveSessionStop, ActiveSession, Strategy, 
    PresetList, PresetSave, Preset, APIResponse, ErrorResponse
)
from app.services.params import get_param_definitions, get_initial_form_data, get_strategies
from app.services.job_store import (
    create_job, start_runner_process, get_job_paths, read_status, 
    tail_text_file, is_pid_running
)
from app.services.live_store import (
    create_live_session, start_live_runner_process, get_live_paths,
    read_live_status, tail_live_text_file, stop_session_pid,
    get_active_session_id, set_active_session_id
)
from app.services.presets_store import load_presets, upsert_preset, delete_preset, normalize_preset_name
from app.api.deps import (
    get_base_dir, validate_job_exists, validate_live_session_exists,
    check_no_active_live_session, update_job_status_if_died, update_live_status_if_died
)
from app.core.config import settings

router = APIRouter()


def _as_utc_iso(dt: datetime) -> str:
    """Convert datetime to UTC ISO string"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


@router.get("/params")
async def api_params() -> Dict[str, Any]:
    """Get parameter definitions and initial values"""
    defs_payload = get_param_definitions()
    initial = get_initial_form_data()
    return {"param_defs": defs_payload, "initial": initial}


@router.get("/strategies")
async def api_strategies() -> Dict[str, List[Strategy]]:
    """Get available strategies"""
    strategies = get_strategies()
    return {"strategies": strategies}


@router.get("/live/active")
async def api_live_active() -> ActiveSession:
    """Get currently active live session"""
    base = get_base_dir()
    active = get_active_session_id(base)
    return ActiveSession(active_session_id=active)


@router.post("/live/run")
async def api_live_run(request: Request) -> LiveSessionStart:
    """Start a new live trading session"""
    base = get_base_dir()
    
    # Check if there's already an active session
    active = get_active_session_id(base)
    if active:
        try:
            paths = get_live_paths(active)
            st = read_live_status(paths)
            if st.get("state") in {"queued", "running"}:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A live session is already running: {active}"
                )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A live session is already running: {active}"
            )
    
    # Parse request body
    try:
        body = await request.body()
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body"
        )
    
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JSON body must be an object"
        )
    
    # Validate and extract parameters
    strategy = str(payload.get("strategy") or "break_retest")
    symbols_raw = payload.get("symbols")
    timeframe = payload.get("timeframe")
    max_candles = payload.get("max_candles")
    
    if not isinstance(symbols_raw, str) or not symbols_raw.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing `symbols`"
        )
    
    symbols = [s.strip() for s in symbols_raw.split(",") if s.strip()]
    if not symbols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one symbol"
        )
    
    if not timeframe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing `timeframe`"
        )
    
    # Build env overrides from payload
    from app.services.params import PARAM_DEFS
    env_overrides: Dict[str, str] = {}
    meta: Dict[str, Any] = {"MODE": "live"}
    
    allowed_env_names = {d.name for d in PARAM_DEFS if d.destination.value == "env"}
    for k, v in payload.items():
        if k in allowed_env_names and v is not None and v != "":
            env_overrides[str(k)] = "True" if isinstance(v, bool) and v else ("False" if isinstance(v, bool) else str(v))
    
    # Ensure MT5 symbol/timeframe match selected live config
    env_overrides["MT5_SYMBOL"] = ",".join(symbols)
    env_overrides["MT5_TIMEFRAME"] = str(timeframe)
    env_overrides.setdefault("MODE", "live")
    
    params = {
        "strategy": strategy,
        "backtest_args": {"symbols": symbols, "timeframe": str(timeframe), "max_candles": max_candles},
        "env_overrides": env_overrides,
        "meta": meta,
    }
    
    session_id, paths = create_live_session(base, params=params)
    set_active_session_id(base, session_id)
    
    pid = start_live_runner_process(base, paths.session_dir, paths.stdout_log, paths.stderr_log)
    from app.services.live_store import write_live_status
    write_live_status(paths, {
        "state": "running", 
        "pid": pid, 
        "python_executable": os.environ.get("BACKTEST_RUNNER_PYTHON") or sys.executable
    })
    
    return LiveSessionStart(
        ok=True,
        session_id=session_id,
        status_url=f"/api/live/{session_id}/status/",
        snapshot_url=f"/api/live/{session_id}/snapshot/",
        stop_url=f"/api/live/{session_id}/stop/"
    )


@router.get("/live/{session_id}/status")
@router.get("/live/{session_id}/status/")
async def api_live_status(session_id: str) -> LiveSessionStatus:
    """Get status of a live session"""
    base = get_base_dir()
    session_info = validate_live_session_exists(session_id)
    paths = session_info["paths"]
    status_data = session_info["status"]
    
    # Handle transient file issues
    if status_data.get("state") == "unknown" and (status_data.get("error") or "").startswith("Failed to read status.json"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Status not ready, retry"
        )
    
    # Update status if process died
    status_data = update_live_status_if_died(paths, status_data)
    
    # Load params if available
    params_payload = None
    try:
        if paths.params_json.exists():
            with open(paths.params_json, 'r') as f:
                params_payload = json.load(f)
    except Exception:
        params_payload = None
    
    return LiveSessionStatus(
        session_id=session_id,
        state=status_data.get("state"),
        created_at=status_data.get("created_at"),
        updated_at=status_data.get("updated_at"),
        pid=status_data.get("pid"),
        python_executable=status_data.get("python_executable"),
        returncode=status_data.get("returncode"),
        error=status_data.get("error"),
        latest_seq=status_data.get("latest_seq"),
        params=params_payload,
        stdout_tail=tail_live_text_file(paths.stdout_log),
        stderr_tail=tail_live_text_file(paths.stderr_log),
        has_snapshot=paths.snapshot_json.exists(),
        snapshot_url=f"/api/live/{session_id}/snapshot/" if paths.snapshot_json.exists() else None
    )


@router.get("/live/{session_id}/snapshot")
@router.get("/live/{session_id}/snapshot/")
async def api_live_snapshot(session_id: str) -> Dict[str, Any]:
    """Get snapshot data for a live session"""
    print(f"DEBUG: Snapshot request for session {session_id}")
    
    session_info = validate_live_session_exists(session_id)
    paths = session_info["paths"]
    
    print(f"DEBUG: Snapshot file exists: {paths.snapshot_json.exists()}")
    print(f"DEBUG: Snapshot file path: {paths.snapshot_json}")
    
    if not paths.snapshot_json.exists():
        print(f"DEBUG: No snapshot yet for session {session_id}, returning empty data")
        # Return empty snapshot data instead of 404
        return {
            "symbols": {},
            "stats": {
                "balance": 0,
                "equity": 0,
                "profit": 0,
                "margin": 0,
                "margin_free": 0
            },
            "meta": {
                "session_dir": str(paths.session_dir),
                "timeframe": "H1",
                "symbols": [],
                "latest_seq": 0,
                "updated_at": None,
                "status": "initializing"
            }
        }
    
    try:
        with open(paths.snapshot_json, 'r') as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Snapshot not ready, retry"
        )


@router.post("/live/{session_id}/stop")
async def api_live_stop(session_id: str) -> LiveSessionStop:
    """Stop a live session"""
    session_info = validate_live_session_exists(session_id)
    paths = session_info["paths"]
    status_data = session_info["status"]
    
    pid = status_data.get("pid")
    killed = stop_session_pid(int(pid) if pid else None)
    
    from app.services.live_store import write_live_status, set_active_session_id
    write_live_status(paths, {"state": "stopped", "returncode": 0 if killed else status_data.get("returncode")})
    
    if get_active_session_id(settings.BASE_DIR) == session_id:
        set_active_session_id(settings.BASE_DIR, None)
    
    return LiveSessionStop(ok=True, killed=bool(killed))


@router.post("/run/")
@router.post("/run")
async def api_run_backtest(request: BacktestRequest) -> Dict[str, Any]:
    """Run a backtest"""
    # Debug: log the request data
    print(f"Received backtest request: {request}")
    print(f"Request dict: {request.dict()}")
    
    base = get_base_dir()
    
    # Convert request to internal format
    backtest_args: Dict[str, Any] = {}
    env_overrides: Dict[str, str] = {}
    meta: Dict[str, Any] = {}
    
    # Process all fields from the request
    for field_name, field_value in request.dict().items():
        if field_value is None:
            continue
            
        if field_name == "symbols":
            backtest_args[field_name] = field_value
        elif field_name in ["start_date", "end_date"]:
            backtest_args[field_name] = _as_utc_iso(field_value)
        elif field_name in ["timeframe", "max_candles", "spread_pips"]:
            backtest_args[field_name] = field_value
        elif field_name in ["strategy"]:
            meta[field_name] = field_value
        elif field_name in ["MODE", "MARKET_TYPE"]:
            meta[field_name] = field_value
        elif isinstance(field_value, bool):
            env_overrides[field_name] = "True" if field_value else "False"
        else:
            env_overrides[field_name] = str(field_value)
    
    env_overrides.setdefault("MODE", "backtest")
    env_overrides.setdefault("MARKET_TYPE", "forex")
    
    params = {"backtest_args": backtest_args, "env_overrides": env_overrides, "meta": meta}
    
    job_id, paths = create_job(base, params=params)
    start_runner_process(base, paths)
    
    return {
        "ok": True,
        "job_id": job_id,
        "job_url": f"/jobs/{job_id}/",
        "status_url": f"/api/jobs/{job_id}/status/",
        "result_url": f"/api/jobs/{job_id}/result/"
    }


@router.get("/jobs/{job_id}/status")
async def job_status(job_id: str) -> JobStatus:
    """Get status of a job"""
    job_info = validate_job_exists(job_id)
    paths = job_info["paths"]
    status_data = job_info["status"]
    
    # Update status if process died
    status_data = update_job_status_if_died(paths, status_data)
    
    # Load params if available
    params_payload = None
    try:
        if paths.params_json.exists():
            with open(paths.params_json, 'r') as f:
                params_payload = json.load(f)
    except Exception:
        params_payload = None
    
    return JobStatus(
        job_id=job_id,
        status=status_data.get("status"),
        created_at=status_data.get("created_at"),
        updated_at=status_data.get("updated_at"),
        pid=status_data.get("pid"),
        python_executable=status_data.get("python_executable"),
        returncode=status_data.get("returncode"),
        error=status_data.get("error"),
        params=params_payload,
        stdout_tail=tail_text_file(paths.stdout_log),
        stderr_tail=tail_text_file(paths.stderr_log),
        has_result=paths.result_json.exists(),
        result_url=f"/api/jobs/{job_id}/result/" if paths.result_json.exists() else None
    )


@router.get("/jobs/{job_id}/result")
async def job_result(job_id: str) -> Dict[str, Any]:
    """Get result of a job"""
    job_info = validate_job_exists(job_id)
    paths = job_info["paths"]
    
    if not paths.result_json.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result not ready"
        )
    
    with open(paths.result_json, 'r') as f:
        data = json.load(f)
    return data


@router.get("/presets")
async def presets_list_or_save() -> PresetList:
    """List all presets"""
    presets = load_presets(settings.BASE_DIR)
    return PresetList(presets=sorted(presets.keys()))


@router.post("/presets")
async def presets_save(request: PresetSave) -> APIResponse:
    """Save a preset"""
    try:
        name = normalize_preset_name(str(request.name))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    upsert_preset(settings.BASE_DIR, name, request.values)
    return APIResponse(ok=True, message=f"Preset '{name}' saved successfully")


@router.get("/presets/{name}")
async def preset_get(name: str) -> Preset:
    """Get a specific preset"""
    try:
        name = normalize_preset_name(name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    presets = load_presets(settings.BASE_DIR)
    if name not in presets:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preset not found"
        )
    
    return Preset(name=name, values=presets[name])


@router.delete("/presets/{name}")
async def preset_delete(name: str) -> APIResponse:
    """Delete a preset"""
    try:
        name = normalize_preset_name(name)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    try:
        delete_preset(settings.BASE_DIR, name)
        return APIResponse(ok=True, message=f"Preset '{name}' deleted successfully")
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preset not found"
        )
