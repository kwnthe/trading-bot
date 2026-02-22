import json
import asyncio
from datetime import datetime
from typing import Dict, List, Set, Any
from fastapi import WebSocket, WebSocketDisconnect
from app.core.config import settings


class ConnectionManager:
    """Manages WebSocket connections for live chart streaming"""
    
    def __init__(self):
        # Store active connections by session_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Store session metadata
        self.session_metadata: Dict[str, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and register a WebSocket connection"""
        await websocket.accept()
        
        # Add connection to session group
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        
        self.active_connections[session_id].add(websocket)
        
        # Store session metadata
        if session_id not in self.session_metadata:
            self.session_metadata[session_id] = {
                "connected_at": datetime.now().isoformat(),
                "connection_count": 0
            }
        
        self.session_metadata[session_id]["connection_count"] += 1
        self.session_metadata[session_id]["last_activity"] = datetime.now().isoformat()
        
        print(f"WebSocket connected for session {session_id}. "
              f"Total connections for session: {len(self.active_connections[session_id])}")
        
        # Send initial connection confirmation
        await self.send_personal_message({
            'type': 'connection_established',
            'session_id': session_id,
            'timestamp': datetime.now().isoformat(),
            'message': 'Connected to live chart stream'
        }, websocket)
    
    def disconnect(self, websocket: WebSocket, session_id: str):
        """Remove a WebSocket connection"""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            
            # Update session metadata
            if session_id in self.session_metadata:
                self.session_metadata[session_id]["connection_count"] = max(
                    0, self.session_metadata[session_id]["connection_count"] - 1
                )
                self.session_metadata[session_id]["last_activity"] = datetime.now().isoformat()
            
            # Clean up empty session groups
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
                if session_id in self.session_metadata:
                    del self.session_metadata[session_id]
            
            print(f"WebSocket disconnected for session {session_id}. "
                  f"Remaining connections: {len(self.active_connections.get(session_id, []))}")
    
    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send a message to a specific WebSocket client"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            print(f"Failed to send personal message: {e}")
    
    async def broadcast_to_session(self, message: Dict[str, Any], session_id: str):
        """Broadcast a message to all clients in a session"""
        if session_id not in self.active_connections:
            return
        
        # Add timestamp if not present
        if 'timestamp' not in message:
            message['timestamp'] = datetime.now().isoformat()
        
        # Add session_id if not present
        if 'session_id' not in message:
            message['session_id'] = session_id
        
        # Send to all connected clients in the session
        disconnected_clients = []
        for connection in self.active_connections[session_id].copy():
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                print(f"Failed to send message to client in session {session_id}: {e}")
                disconnected_clients.append(connection)
        
        # Remove disconnected clients
        for client in disconnected_clients:
            self.disconnect(client, session_id)
    
    async def broadcast_chart_update(self, session_id: str, chart_data: Dict[str, Any]):
        """Send chart update to all clients in a session"""
        message = {
            'type': 'chart_update',
            'data': chart_data
        }
        await self.broadcast_to_session(message, session_id)
    
    async def broadcast_status_update(self, session_id: str, status_data: Dict[str, Any]):
        """Send status update to all clients in a session"""
        message = {
            'type': 'status_update',
            'status': status_data
        }
        await self.broadcast_to_session(message, session_id)
    
    async def broadcast_error(self, session_id: str, error_message: str):
        """Send error message to all clients in a session"""
        message = {
            'type': 'error',
            'message': error_message
        }
        await self.broadcast_to_session(message, session_id)
    
    async def handle_client_message(self, websocket: WebSocket, session_id: str, message: Dict[str, Any]):
        """Handle incoming message from client"""
        message_type = message.get('type')
        
        if message_type == 'ping':
            await self.send_personal_message({
                'type': 'pong',
                'timestamp': datetime.now().isoformat()
            }, websocket)
        
        elif message_type == 'subscribe':
            # Handle subscription to specific data types
            await self.send_personal_message({
                'type': 'subscription_confirmed',
                'session_id': session_id,
                'subscribed_to': message.get('data_types', ['all']),
                'timestamp': datetime.now().isoformat()
            }, websocket)
        
        else:
            # Unknown message type
            await self.send_personal_message({
                'type': 'error',
                'message': f'Unknown message type: {message_type}'
            }, websocket)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about active sessions"""
        return {
            "active_sessions": len(self.active_connections),
            "total_connections": sum(len(conns) for conns in self.active_connections.values()),
            "session_details": {
                session_id: {
                    "connection_count": len(connections),
                    "metadata": self.session_metadata.get(session_id, {})
                }
                for session_id, connections in self.active_connections.items()
            }
        }
    
    async def cleanup_inactive_sessions(self, max_inactive_minutes: int = 60):
        """Clean up inactive sessions"""
        from datetime import timedelta
        
        cutoff_time = datetime.now() - timedelta(minutes=max_inactive_minutes)
        sessions_to_remove = []
        
        for session_id, metadata in self.session_metadata.items():
            last_activity_str = metadata.get("last_activity", metadata.get("connected_at"))
            if last_activity_str:
                try:
                    last_activity = datetime.fromisoformat(last_activity_str.replace('Z', '+00:00'))
                    if last_activity < cutoff_time:
                        sessions_to_remove.append(session_id)
                except:
                    pass
        
        for session_id in sessions_to_remove:
            if session_id in self.active_connections:
                # Close all connections for this session
                for websocket in self.active_connections[session_id].copy():
                    try:
                        await websocket.close()
                    except:
                        pass
                del self.active_connections[session_id]
            
            if session_id in self.session_metadata:
                del self.session_metadata[session_id]
            
            print(f"Cleaned up inactive session: {session_id}")


# Global connection manager instance
manager = ConnectionManager()


# Helper function for external processes (like run_live.py)
async def send_chart_update(session_id: str, chart_data: Dict[str, Any]):
    """Send chart update to all clients in a session (can be called from external processes)"""
    await manager.broadcast_chart_update(session_id, chart_data)


# Synchronous wrapper for external processes
def broadcast_chart_update(session_id: str, chart_data: Dict[str, Any]):
    """Synchronous wrapper for broadcasting chart updates"""
    try:
        # Try to get the current event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            asyncio.create_task(send_chart_update(session_id, chart_data))
        except RuntimeError:
            # If we're in sync context, run the coroutine
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(send_chart_update(session_id, chart_data))
            loop.close()
    except Exception as e:
        print(f"Warning: Failed to broadcast chart update: {e}")
        # Don't raise exception to avoid breaking live trading
