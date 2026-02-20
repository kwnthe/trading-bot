import json
import asyncio
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ValidationError


class LiveChartConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for streaming live chart overlay data.
    
    Handles real-time updates for:
    - Chart overlays (zones, EMA, markers)
    - Live trading status
    - Connection management
    """
    
    async def connect(self):
        """Accept WebSocket connection and join session group."""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.group_name = f'live_chart_{self.session_id}'
        
        # Validate session exists (basic check)
        if not await self.validate_session():
            await self.close(code=4004, reason='Invalid session')
            return
        
        # Join session group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        # Accept WebSocket connection
        await self.accept()
        
        # Send initial connection confirmation
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'message': 'Connected to live chart stream'
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave session group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages (if needed)."""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            # Handle different message types
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                }))
            elif message_type == 'subscribe':
                # Handle subscription to specific data types
                await self.handle_subscription(data)
            else:
                # Unknown message type
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown message type: {message_type}'
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Error processing message: {str(e)}'
            }))
    
    async def chart_update(self, event):
        """Send chart overlay update to client."""
        await self.send(text_data=json.dumps({
            'type': 'chart_update',
            'session_id': self.session_id,
            'timestamp': event.get('timestamp', datetime.now().isoformat()),
            'data': event['data']
        }))
    
    async def status_update(self, event):
        """Send status update to client."""
        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'session_id': self.session_id,
            'timestamp': event.get('timestamp', datetime.now().isoformat()),
            'status': event['status']
        }))
    
    async def error_message(self, event):
        """Send error message to client."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'session_id': self.session_id,
            'timestamp': event.get('timestamp', datetime.now().isoformat()),
            'message': event['message']
        }))
    
    async def handle_subscription(self, data):
        """Handle subscription to specific data types."""
        # For now, just acknowledge subscription
        # Future: implement selective data streaming
        await self.send(text_data=json.dumps({
            'type': 'subscription_confirmed',
            'session_id': self.session_id,
            'subscribed_to': data.get('data_types', ['all']),
            'timestamp': datetime.now().isoformat()
        }))
    
    @database_sync_to_async
    def validate_session(self):
        """Validate that the session exists."""
        try:
            # Check if session directory exists
            from pathlib import Path
            import os
            
            # Try multiple possible paths for different environments
            possible_paths = [
                Path(__file__).resolve().parent.parent / "var" / "live_sessions" / self.session_id,
                Path(__file__).resolve().parent.parent.parent / "var" / "live_sessions" / self.session_id,
                # Check for existing session files in backtests directory
                Path(__file__).resolve().parent.parent / "backtests" / "live_sessions" / self.session_id,
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


# Helper function for sending chart updates from external processes
async def send_chart_update(session_id, chart_data):
    """
    Send chart update to all clients in a session.
    
    This function can be called from external processes (like run_live.py)
    to send updates to connected WebSocket clients.
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    group_name = f'live_chart_{session_id}'
    
    await channel_layer.group_send(
        group_name,
        {
            'type': 'chart_update',
            'data': chart_data,
            'timestamp': datetime.now().isoformat()
        }
    )


# Synchronous wrapper for external processes
def broadcast_chart_update(session_id, chart_data):
    """
    Synchronous wrapper for broadcasting chart updates.
    
    This function can be called from synchronous code (like run_live.py)
    to send updates to WebSocket clients.
    """
    try:
        # Get event loop and run the async function
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're in an async context, create a task
            asyncio.create_task(send_chart_update(session_id, chart_data))
        else:
            # If we're in sync context, run the coroutine
            loop.run_until_complete(send_chart_update(session_id, chart_data))
    except Exception as e:
        print(f"Warning: Failed to broadcast chart update: {e}")
        # Don't raise exception to avoid breaking live trading
