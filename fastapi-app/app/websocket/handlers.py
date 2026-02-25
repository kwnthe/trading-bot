import asyncio
import json
from pathlib import Path
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from typing import Any, Dict, Optional

from .connection_manager import manager
from app.services.live_store import get_live_paths, read_live_status
from app.utils.file_utils import read_text_file
from app.core.config import settings

POLL_INTERVAL = 2  # seconds between file checks


def _read_json_safe(path: Path) -> Optional[Dict[str, Any]]:
    """Read a JSON file, return None on any error."""
    try:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _file_mtime(path: Path) -> float:
    """Return mtime of a file, or 0 if it doesn't exist."""
    try:
        return path.stat().st_mtime if path.exists() else 0
    except Exception:
        return 0


async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for live sessions.

    Pushes file changes (status, snapshot, stdout, stderr) to the
    client every POLL_INTERVAL seconds.  Also handles incoming
    ping / subscribe messages from the client.
    """
    print(f"DEBUG: WebSocket endpoint called for session {session_id}")
    await websocket.accept()
    print(f"DEBUG: WebSocket accepted for session {session_id}")

    # Resolve session paths
    session_dir = settings.LIVE_DIR / session_id
    if not session_dir.exists():
        await websocket.send_json({
            "type": "error",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "message": f"Session {session_id} not found",
        })
        await websocket.close(code=4004, reason="Session not found")
        return

    status_path = session_dir / "status.json"
    snapshot_path = session_dir / "snapshot.json"
    stdout_path = session_dir / "stdout.log"
    stderr_path = session_dir / "stderr.log"
    overlay_path = session_dir / "chart_overlays.json"
    params_path = session_dir / "params.json"

    # Send connection confirmation
    await websocket.send_json({
        "type": "connection_established",
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "message": "Connected to live session stream",
    })

    await manager.connect(websocket, session_id)

    # Track mtimes to only send when files change
    last_status_mtime = 0.0
    last_snapshot_mtime = 0.0
    last_stdout_mtime = 0.0
    last_stderr_mtime = 0.0
    last_overlay_mtime = 0.0

    async def push_updates():
        """Check files and push changes to client."""
        nonlocal last_status_mtime, last_snapshot_mtime
        nonlocal last_stdout_mtime, last_stderr_mtime, last_overlay_mtime

        # ── status.json ──
        mt = _file_mtime(status_path)
        if mt > last_status_mtime:
            last_status_mtime = mt
            data = _read_json_safe(status_path)
            if data is not None:
                # Attach stdout / stderr / params
                data["stdout"] = read_text_file(stdout_path) or ""
                data["stderr"] = read_text_file(stderr_path) or ""
                data["session_id"] = session_id
                data["has_snapshot"] = snapshot_path.exists()

                params = _read_json_safe(params_path)
                if params:
                    data["params"] = params

                await websocket.send_json({
                    "type": "status_update",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "status": data,
                })

        # ── stdout / stderr changes without status change ──
        stdout_mt = _file_mtime(stdout_path)
        stderr_mt = _file_mtime(stderr_path)
        if stdout_mt > last_stdout_mtime or stderr_mt > last_stderr_mtime:
            last_stdout_mtime = stdout_mt
            last_stderr_mtime = stderr_mt
            # Only send logs update if status didn't already include them
            if mt <= last_status_mtime - 0.001:  # status wasn't just sent
                await websocket.send_json({
                    "type": "logs_update",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "stdout": read_text_file(stdout_path) or "",
                    "stderr": read_text_file(stderr_path) or "",
                })

        # ── snapshot.json ──
        mt = _file_mtime(snapshot_path)
        if mt > last_snapshot_mtime:
            last_snapshot_mtime = mt
            data = _read_json_safe(snapshot_path)
            if data is not None:
                await websocket.send_json({
                    "type": "snapshot_update",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "snapshot": data,
                })

    try:
        # Send initial data immediately
        try:
            await push_updates()
        except Exception as e:
            print(f"Error in initial push_updates for session {session_id}: {e}")
            await websocket.close(code=1011, reason="Initial data push failed")
            return

        while True:
            # Wait for either a client message or the poll interval
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=POLL_INTERVAL
                )
                # Handle client message
                try:
                    message = json.loads(data)
                    msg_type = message.get("type")
                    if msg_type == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat(),
                        })
                    elif msg_type == "request_snapshot":
                        last_snapshot_mtime = 0  # force re-send
                    elif msg_type == "request_status":
                        last_status_mtime = 0  # force re-send
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # No client message within poll interval – that's fine
                pass

            # Push any file changes
            await push_updates()

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        print(f"WebSocket error for session {session_id}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        manager.disconnect(websocket, session_id)
