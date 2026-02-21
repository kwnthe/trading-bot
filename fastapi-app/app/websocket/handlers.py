import json
from pathlib import Path
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Any

from .connection_manager import manager
from app.services.live_store import get_live_paths, read_live_status
from app.core.config import settings


async def validate_session(session_id: str) -> bool:
    """Validate that the session exists"""
    try:
        # Check if session directory exists
        possible_paths = [
            settings.LIVE_DIR / session_id,
            settings.BASE_DIR / "web-app" / "var" / "live" / session_id,
        ]
        
        for path in possible_paths:
            if path.exists():
                return True
        
        # For development, allow any session ID
        # In production, implement proper session validation
        return True
        
    except Exception:
        # If validation fails, allow connection for development
        return True


async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for streaming live chart overlay data.
    
    Handles real-time updates for:
    - Chart overlays (zones, EMA, markers)
    - Live trading status
    - Connection management
    """
    print(f"DEBUG: WebSocket connection attempt for session {session_id}")
    
    # Validate session exists (basic check)
    if not await validate_session(session_id):
        print(f"DEBUG: Session validation failed for {session_id}")
        await websocket.close(code=4004, reason='Invalid session')
        return
    
    print(f"DEBUG: Session validated, accepting WebSocket connection for {session_id}")
    
    # Connect the WebSocket
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message from client
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                await manager.handle_client_message(websocket, session_id, message)
                
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await manager.send_personal_message({
                    'type': 'error',
                    'message': 'Invalid JSON format'
                }, websocket)
            except Exception as e:
                await manager.send_personal_message({
                    'type': 'error',
                    'message': f'Error processing message: {str(e)}'
                }, websocket)
    
    except WebSocketDisconnect:
        pass
    finally:
        # Disconnect the WebSocket
        manager.disconnect(websocket, session_id)


async def get_session_status(session_id: str) -> Dict[str, Any]:
    """Get current session status for WebSocket clients"""
    try:
        paths = get_live_paths(session_id)
        status = read_live_status(paths)
        return status
    except Exception:
        return {"state": "unknown", "error": "Failed to read session status"}
