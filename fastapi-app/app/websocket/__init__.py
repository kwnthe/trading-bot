from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from .handlers import websocket_endpoint

websocket_router = APIRouter()

# WebSocket route for live chart streaming
websocket_router.add_websocket_route(
    "/ws/live/{session_id}", 
    websocket_endpoint,
    name="live_chart_websocket"
)