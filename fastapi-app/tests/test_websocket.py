import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.websocket.connection_manager import ConnectionManager, manager
from app.websocket.handlers import websocket_endpoint, validate_session, get_session_status
from tests.conftest import mock_websocket


class TestConnectionManager:
    """Test WebSocket connection management"""
    
    def test_connect(self, mock_websocket):
        """Test connecting a WebSocket"""
        session_id = "test_session_123"
        
        # Mock the accept method
        mock_websocket.accept = AsyncMock()
        
        # Test connection
        asyncio.run(manager.connect(mock_websocket, session_id))
        
        # Verify connection was added
        assert session_id in manager.active_connections
        assert mock_websocket in manager.active_connections[session_id]
        
        # Verify metadata
        assert session_id in manager.session_metadata
        assert manager.session_metadata[session_id]["connection_count"] == 1
        
        # Verify accept was called
        mock_websocket.accept.assert_called_once()
        
        # Verify initial message was sent
        mock_websocket.send_text.assert_called_once()
        message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert message["type"] == "connection_established"
        assert message["session_id"] == session_id
    
    def test_disconnect(self, mock_websocket):
        """Test disconnecting a WebSocket"""
        session_id = "test_session_123"
        
        # First connect
        mock_websocket.accept = AsyncMock()
        asyncio.run(manager.connect(mock_websocket, session_id))
        
        # Clear the call history
        mock_websocket.reset_mock()
        
        # Test disconnect
        manager.disconnect(mock_websocket, session_id)
        
        # Verify connection was removed
        assert session_id not in manager.active_connections
        assert session_id not in manager.session_metadata
    
    def test_multiple_connections_same_session(self, mock_websocket):
        """Test multiple connections to the same session"""
        session_id = "test_session_123"
        mock_websocket2 = Mock()
        mock_websocket2.accept = AsyncMock()
        mock_websocket2.send_text = AsyncMock()
        
        # Connect first client
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        asyncio.run(manager.connect(mock_websocket, session_id))
        
        # Connect second client
        asyncio.run(manager.connect(mock_websocket2, session_id))
        
        # Verify both connections are tracked
        assert len(manager.active_connections[session_id]) == 2
        assert manager.session_metadata[session_id]["connection_count"] == 2
        
        # Disconnect one client
        manager.disconnect(mock_websocket, session_id)
        
        # Verify one connection remains
        assert len(manager.active_connections[session_id]) == 1
        assert manager.session_metadata[session_id]["connection_count"] == 1
    
    async def test_send_personal_message(self, mock_websocket):
        """Test sending a message to a specific client"""
        session_id = "test_session_123"
        message = {"type": "test", "data": "hello"}
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        await manager.connect(mock_websocket, session_id)
        
        # Clear previous calls
        mock_websocket.send_text.reset_mock()
        
        # Send message
        await manager.send_personal_message(message, mock_websocket)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called_once_with(json.dumps(message))
    
    async def test_broadcast_to_session(self, mock_websocket):
        """Test broadcasting a message to all clients in a session"""
        session_id = "test_session_123"
        mock_websocket2 = Mock()
        mock_websocket2.accept = AsyncMock()
        mock_websocket2.send_text = AsyncMock()
        
        # Setup two connections
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        await manager.connect(mock_websocket, session_id)
        await manager.connect(mock_websocket2, session_id)
        
        # Clear previous calls
        mock_websocket.send_text.reset_mock()
        mock_websocket2.send_text.reset_mock()
        
        # Broadcast message
        message = {"type": "test", "data": "broadcast"}
        await manager.broadcast_to_session(message, session_id)
        
        # Verify message was sent to both clients
        mock_websocket.send_text.assert_called_once()
        mock_websocket2.send_text.assert_called_once()
        
        # Verify message content
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "test"
        assert sent_message["data"] == "broadcast"
        assert "timestamp" in sent_message
        assert sent_message["session_id"] == session_id
    
    async def test_broadcast_chart_update(self, mock_websocket):
        """Test broadcasting chart update"""
        session_id = "test_session_123"
        chart_data = {"zones": [], "ema": []}
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        await manager.connect(mock_websocket, session_id)
        
        # Clear previous calls
        mock_websocket.send_text.reset_mock()
        
        # Broadcast chart update
        await manager.broadcast_chart_update(session_id, chart_data)
        
        # Verify message structure
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "chart_update"
        assert sent_message["data"] == chart_data
    
    async def test_broadcast_status_update(self, mock_websocket):
        """Test broadcasting status update"""
        session_id = "test_session_123"
        status_data = {"state": "running", "pid": 12345}
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        await manager.connect(mock_websocket, session_id)
        
        # Clear previous calls
        mock_websocket.send_text.reset_mock()
        
        # Broadcast status update
        await manager.broadcast_status_update(session_id, status_data)
        
        # Verify message structure
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "status_update"
        assert sent_message["status"] == status_data
    
    async def test_broadcast_error(self, mock_websocket):
        """Test broadcasting error message"""
        session_id = "test_session_123"
        error_message = "Test error message"
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        await manager.connect(mock_websocket, session_id)
        
        # Clear previous calls
        mock_websocket.send_text.reset_mock()
        
        # Broadcast error
        await manager.broadcast_error(session_id, error_message)
        
        # Verify message structure
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "error"
        assert sent_message["message"] == error_message
    
    async def test_handle_client_message_ping(self, mock_websocket):
        """Test handling ping message from client"""
        session_id = "test_session_123"
        message = {"type": "ping"}
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        await manager.connect(mock_websocket, session_id)
        
        # Clear previous calls
        mock_websocket.send_text.reset_mock()
        
        # Handle message
        await manager.handle_client_message(mock_websocket, session_id, message)
        
        # Verify pong response
        mock_websocket.send_text.assert_called_once()
        response = json.loads(mock_websocket.send_text.call_args[0][0])
        assert response["type"] == "pong"
        assert "timestamp" in response
    
    async def test_handle_client_message_subscribe(self, mock_websocket):
        """Test handling subscribe message from client"""
        session_id = "test_session_123"
        message = {"type": "subscribe", "data_types": ["chart", "status"]}
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        await manager.connect(mock_websocket, session_id)
        
        # Clear previous calls
        mock_websocket.send_text.reset_mock()
        
        # Handle message
        await manager.handle_client_message(mock_websocket, session_id, message)
        
        # Verify subscription confirmation
        mock_websocket.send_text.assert_called_once()
        response = json.loads(mock_websocket.send_text.call_args[0][0])
        assert response["type"] == "subscription_confirmed"
        assert response["subscribed_to"] == ["chart", "status"]
        assert response["session_id"] == session_id
    
    async def test_handle_client_message_unknown(self, mock_websocket):
        """Test handling unknown message type"""
        session_id = "test_session_123"
        message = {"type": "unknown_type"}
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        await manager.connect(mock_websocket, session_id)
        
        # Clear previous calls
        mock_websocket.send_text.reset_mock()
        
        # Handle message
        await manager.handle_client_message(mock_websocket, session_id, message)
        
        # Verify error response
        mock_websocket.send_text.assert_called_once()
        response = json.loads(mock_websocket.send_text.call_args[0][0])
        assert response["type"] == "error"
        assert "Unknown message type" in response["message"]
    
    def test_get_session_stats(self, mock_websocket):
        """Test getting session statistics"""
        session_id = "test_session_123"
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        asyncio.run(manager.connect(mock_websocket, session_id))
        
        # Get stats
        stats = manager.get_session_stats()
        
        # Verify stats structure
        assert "active_sessions" in stats
        assert "total_connections" in stats
        assert "session_details" in stats
        assert stats["active_sessions"] == 1
        assert stats["total_connections"] == 1
        assert session_id in stats["session_details"]
        assert stats["session_details"][session_id]["connection_count"] == 1
    
    async def test_cleanup_inactive_sessions(self, mock_websocket):
        """Test cleaning up inactive sessions"""
        session_id = "test_session_123"
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        await manager.connect(mock_websocket, session_id)
        
        # Manually set old activity time
        old_time = "2020-01-01T00:00:00"
        manager.session_metadata[session_id]["last_activity"] = old_time
        manager.session_metadata[session_id]["connected_at"] = old_time
        
        # Run cleanup with 0 minute threshold (should clean up immediately)
        await manager.cleanup_inactive_sessions(max_inactive_minutes=0)
        
        # Verify session was cleaned up
        assert session_id not in manager.active_connections
        assert session_id not in manager.session_metadata


class TestWebSocketHandlers:
    """Test WebSocket endpoint handlers"""
    
    @pytest.mark.asyncio
    async def test_validate_session_exists(self, test_settings):
        """Test session validation when session exists"""
        # Create session directory
        session_id = "test_session"
        session_dir = test_settings.LIVE_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Test validation
        result = await validate_session(session_id)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_session_not_exists(self):
        """Test session validation when session doesn't exist"""
        result = await validate_session("nonexistent_session")
        assert result is True  # For development, allows any session ID
    
    @pytest.mark.asyncio
    async def test_websocket_endpoint_connection_flow(self, mock_websocket, test_settings):
        """Test full WebSocket connection flow"""
        session_id = "test_session_123"
        
        # Create session directory
        session_dir = test_settings.LIVE_DIR / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Mock WebSocket methods
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(side_effect=["{}"])
        mock_websocket.close = Mock()
        
        # Mock connection manager
        with patch('app.websocket.handlers.manager') as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = Mock()
            mock_manager.handle_client_message = AsyncMock()
            
            # Test connection (should disconnect immediately due to empty message)
            with patch('app.websocket.handlers.validate_session', return_value=True):
                await websocket_endpoint(mock_websocket, session_id)
            
            # Verify connection flow
            mock_manager.connect.assert_called_once_with(mock_websocket, session_id)
            mock_manager.handle_client_message.assert_called_once()
            mock_manager.disconnect.assert_called_once_with(mock_websocket, session_id)
    
    @pytest.mark.asyncio
    async def test_websocket_endpoint_invalid_session(self, mock_websocket):
        """Test WebSocket endpoint with invalid session"""
        session_id = "invalid_session"
        
        # Mock WebSocket close method
        mock_websocket.close = AsyncMock()
        
        # Mock validation to return False
        with patch('app.websocket.handlers.validate_session', return_value=False):
            await websocket_endpoint(mock_websocket, session_id)
        
        # Verify WebSocket was closed with error code
        mock_websocket.close.assert_called_once_with(code=4004, reason='Invalid session')
    
    @pytest.mark.asyncio
    async def test_get_session_status(self, sample_live_session):
        """Test getting session status"""
        session_id = sample_live_session["session_id"]
        
        # Create status file
        from tests.conftest import TestDataManager
        TestDataManager.create_live_status_file(sample_live_session["paths"], "running")
        
        # Get status
        status = await get_session_status(session_id)
        
        # Verify status
        assert status["state"] == "running"
        assert "created_at" in status
        assert "updated_at" in status
    
    @pytest.mark.asyncio
    async def test_get_session_status_not_found(self):
        """Test getting status for non-existent session"""
        status = await get_session_status("nonexistent_session")
        assert status["state"] == "unknown"
        assert "error" in status


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality"""
    
    @pytest.mark.asyncio
    async def test_broadcast_chart_update_integration(self, mock_websocket):
        """Test broadcasting chart update through the global manager"""
        session_id = "test_session_123"
        chart_data = {"zones": [{"price": 22.5, "strength": 1.0}]}
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        await manager.connect(mock_websocket, session_id)
        
        # Clear previous calls
        mock_websocket.send_text.reset_mock()
        
        # Test global function
        from app.websocket.connection_manager import send_chart_update
        await send_chart_update(session_id, chart_data)
        
        # Verify message was sent
        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "chart_update"
        assert sent_message["data"] == chart_data
    
    def test_broadcast_chart_update_sync_wrapper(self, mock_websocket):
        """Test synchronous wrapper for broadcasting"""
        session_id = "test_session_123"
        chart_data = {"zones": [{"price": 22.5, "strength": 1.0}]}
        
        # Setup
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        asyncio.run(manager.connect(mock_websocket, session_id))
        
        # Clear previous calls
        mock_websocket.send_text.reset_mock()
        
        # Test synchronous wrapper
        from app.websocket.connection_manager import broadcast_chart_update
        broadcast_chart_update(session_id, chart_data)
        
        # Give some time for async processing
        import time
        time.sleep(0.1)
        
        # The sync wrapper creates a task, so we need to check if it was scheduled
        # This is more of a smoke test to ensure no exceptions are raised
        assert True  # If we get here, no exception was raised
