import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models.schemas import (
    BacktestRequest, LiveTradingRequest, JobStatus, LiveSessionStatus,
    LiveSessionStart, LiveSessionStop, ActiveSession, Strategy,
    PresetList, PresetSave, Preset, MarkerRequest, LiveDataSession,
    LiveDataSummary, LiveDataSessions, WebSocketMessage, WebSocketResponse,
    APIResponse, ErrorResponse, FieldType, Destination
)


class TestSchemasValidation:
    """Test Pydantic schema validation"""
    
    def test_backtest_request_valid(self):
        """Test valid backtest request"""
        request_data = {
            "strategy": "break_retest",
            "symbols": "XAGUSD,XAUUSD",
            "timeframe": "H1",
            "max_candles": 1000,
            "start_date": datetime.now(timezone.utc),
            "end_date": datetime.now(timezone.utc),
            "spread_pips": 0.5,
            "RR": 2.0,
            "INITIAL_EQUITY": 10000.0,
            "RISK_PER_TRADE": 0.02,
            "BREAKOUT_LOOKBACK_PERIOD": 20,
            "ZONE_INVERSION_MARGIN_ATR": 0.5,
            "BREAKOUT_MIN_STRENGTH_ATR": 1.0,
            "MIN_RISK_DISTANCE_ATR": 1.0,
            "SR_CANCELLATION_THRESHOLD_ATR": 0.5,
            "SL_BUFFER_ATR": 0.2,
            "EMA_LENGTH": 20,
            "CHECK_FOR_DAILY_RSI": True,
            "BACKTEST_FETCH_CSV_URL": "http://example.com/data",
            "MT5_LOGIN": 123456,
            "MT5_PASSWORD": "password123",
            "MT5_SERVER": "server_name",
            "MT5_PATH": "/path/to/mt5",
            "MODE": "backtest",
            "MARKET_TYPE": "forex"
        }
        
        request = BacktestRequest(**request_data)
        
        assert request.strategy == "break_retest"
        assert request.symbols == ["XAGUSD", "XAUUSD"]
        assert request.timeframe == "H1"
        assert request.max_candles == 1000
        assert request.RR == 2.0
        assert request.CHECK_FOR_DAILY_RSI is True
    
    def test_backtest_request_invalid_symbols(self):
        """Test backtest request with invalid symbols"""
        request_data = {
            "strategy": "break_retest",
            "symbols": "",  # Empty symbols should fail
            "timeframe": "H1",
            "start_date": datetime.now(timezone.utc),
            "end_date": datetime.now(timezone.utc),
            "RR": 2.0,
            "INITIAL_EQUITY": 10000.0,
            "RISK_PER_TRADE": 0.02,
            "BREAKOUT_LOOKBACK_PERIOD": 20,
            "ZONE_INVERSION_MARGIN_ATR": 0.5,
            "BREAKOUT_MIN_STRENGTH_ATR": 1.0,
            "MIN_RISK_DISTANCE_ATR": 1.0,
            "SR_CANCELLATION_THRESHOLD_ATR": 0.5,
            "SL_BUFFER_ATR": 0.2,
            "EMA_LENGTH": 20,
            "MODE": "backtest",
            "MARKET_TYPE": "forex"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            BacktestRequest(**request_data)
        
        assert "Provide at least one symbol" in str(exc_info.value)
    
    def test_live_trading_request_valid(self):
        """Test valid live trading request"""
        request_data = {
            "strategy": "break_retest",
            "symbols": "XAGUSD",
            "timeframe": "M15",
            "RR": 3.0,
            "INITIAL_EQUITY": 5000.0,
            "RISK_PER_TRADE": 0.01,
            "EMA_LENGTH": 50,
            "CHECK_FOR_DAILY_RSI": False
        }
        
        request = LiveTradingRequest(**request_data)
        
        assert request.strategy == "break_retest"
        assert request.symbols == ["XAGUSD"]
        assert request.timeframe == "M15"
        assert request.RR == 3.0
        assert request.CHECK_FOR_DAILY_RSI is False
    
    def test_live_trading_request_minimal(self):
        """Test live trading request with minimal required fields"""
        request_data = {
            "strategy": "break_retest",
            "symbols": "XAGUSD",
            "timeframe": "H1"
        }
        
        request = LiveTradingRequest(**request_data)
        
        assert request.strategy == "break_retest"
        assert request.symbols == ["XAGUSD"]
        assert request.timeframe == "H1"
        assert request.RR is None  # Optional field
        assert request.INITIAL_EQUITY is None  # Optional field
    
    def test_job_status_valid(self):
        """Test valid job status"""
        status_data = {
            "job_id": "test-job-123",
            "status": "running",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "pid": 12345,
            "python_executable": "/usr/bin/python3",
            "returncode": None,
            "error": None,
            "params": {"symbols": ["XAGUSD"]},
            "stdout_tail": "Starting backtest...",
            "stderr_tail": "",
            "has_result": False,
            "result_url": None
        }
        
        status = JobStatus(**status_data)
        
        assert status.job_id == "test-job-123"
        assert status.status == "running"
        assert status.pid == 12345
        assert status.has_result is False
    
    def test_live_session_status_valid(self):
        """Test valid live session status"""
        status_data = {
            "session_id": "test-session-123",
            "state": "running",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "pid": 54321,
            "python_executable": "/usr/bin/python3",
            "returncode": None,
            "error": None,
            "latest_seq": 42,
            "params": {"symbols": ["XAGUSD"]},
            "stdout_tail": "Starting live trading...",
            "stderr_tail": "",
            "has_snapshot": True,
            "snapshot_url": "/api/live/test-session-123/snapshot/"
        }
        
        status = LiveSessionStatus(**status_data)
        
        assert status.session_id == "test-session-123"
        assert status.state == "running"
        assert status.latest_seq == 42
        assert status.has_snapshot is True
    
    def test_live_session_start_valid(self):
        """Test valid live session start response"""
        start_data = {
            "ok": True,
            "session_id": "new-session-123",
            "status_url": "/api/live/new-session-123/status/",
            "snapshot_url": "/api/live/new-session-123/snapshot/",
            "stop_url": "/api/live/new-session-123/stop/"
        }
        
        start = LiveSessionStart(**start_data)
        
        assert start.ok is True
        assert start.session_id == "new-session-123"
        assert "status" in start.status_url
        assert "snapshot" in start.snapshot_url
        assert "stop" in start.stop_url
    
    def test_live_session_stop_valid(self):
        """Test valid live session stop response"""
        stop_data = {
            "ok": True,
            "killed": True
        }
        
        stop = LiveSessionStop(**stop_data)
        
        assert stop.ok is True
        assert stop.killed is True
    
    def test_active_session_valid(self):
        """Test active session response"""
        active_data = {
            "active_session_id": "session-123"
        }
        
        active = ActiveSession(**active_data)
        assert active.active_session_id == "session-123"
        
        # Test with None
        active_none = ActiveSession(active_session_id=None)
        assert active_none.active_session_id is None
    
    def test_strategy_valid(self):
        """Test strategy model"""
        strategy_data = {
            "id": "break_retest",
            "label": "Break + Retest"
        }
        
        strategy = Strategy(**strategy_data)
        assert strategy.id == "break_retest"
        assert strategy.label == "Break + Retest"
    
    def test_preset_list_valid(self):
        """Test preset list model"""
        preset_list_data = {
            "presets": ["preset1", "preset2", "preset3"]
        }
        
        preset_list = PresetList(**preset_list_data)
        assert len(preset_list.presets) == 3
        assert "preset1" in preset_list.presets
    
    def test_preset_save_valid(self):
        """Test preset save model"""
        preset_save_data = {
            "name": "my_preset",
            "values": {
                "symbols": "XAGUSD,XAUUSD",
                "timeframe": "H1",
                "RR": 2.0,
                "INITIAL_EQUITY": 10000
            }
        }
        
        preset_save = PresetSave(**preset_save_data)
        assert preset_save.name == "my_preset"
        assert preset_save.values["RR"] == 2.0
        assert preset_save.values["symbols"] == "XAGUSD,XAUUSD"
    
    def test_preset_valid(self):
        """Test preset model"""
        preset_data = {
            "name": "test_preset",
            "values": {
                "symbols": "EURUSD",
                "timeframe": "M15",
                "RR": 3.0
            }
        }
        
        preset = Preset(**preset_data)
        assert preset.name == "test_preset"
        assert preset.values["timeframe"] == "M15"
    
    def test_marker_request_valid(self):
        """Test marker request model"""
        marker_data = {
            "time": 1640995200,
            "value": 22.5,
            "marker_type": "support",
            "metadata": {
                "note": "Test support level",
                "strength": 1.0
            }
        }
        
        marker = MarkerRequest(**marker_data)
        assert marker.time == 1640995200
        assert marker.value == 22.5
        assert marker.marker_type == "support"
        assert marker.metadata["note"] == "Test support level"
        
        # Test with minimal data
        minimal_marker = MarkerRequest(
            time=1640995200,
            value=22.5,
            marker_type="resistance"
        )
        assert minimal_marker.metadata == {}
    
    def test_marker_request_invalid(self):
        """Test marker request with invalid data"""
        # Missing required field
        with pytest.raises(ValidationError):
            MarkerRequest(
                time=1640995200,
                value=22.5
                # Missing marker_type
            )
    
    def test_live_data_session_valid(self):
        """Test live data session model"""
        session_data = {
            "uuid": "session-123",
            "symbol": "XAGUSD",
            "timeframe": "H1",
            "last_updated": 1640995200,
            "created_at": 1640995000,
            "file_size": 1024
        }
        
        session = LiveDataSession(**session_data)
        assert session.uuid == "session-123"
        assert session.symbol == "XAGUSD"
        assert session.file_size == 1024
    
    def test_live_data_summary_valid(self):
        """Test live data summary model"""
        summary_data = {
            "uuid": "summary-123",
            "symbol": "XAGUSD",
            "timeframe": "H1",
            "last_updated": 1640995200,
            "candles_count": 100,
            "support_zones_count": 5,
            "resistance_zones_count": 3,
            "ema_points_count": 50,
            "markers_count": 8,
            "breakouts_count": 2,
            "events_count": 15,
            "custom_indicators": ["RSI", "MACD"],
            "file_size": 2048
        }
        
        summary = LiveDataSummary(**summary_data)
        assert summary.uuid == "summary-123"
        assert summary.candles_count == 100
        assert summary.custom_indicators == ["RSI", "MACD"]
    
    def test_live_data_sessions_valid(self):
        """Test live data sessions model"""
        sessions_data = {
            "sessions": [
                {
                    "uuid": "session-1",
                    "symbol": "XAGUSD",
                    "timeframe": "H1",
                    "last_updated": 1640995200,
                    "created_at": 1640995000,
                    "file_size": 1024
                },
                {
                    "uuid": "session-2",
                    "symbol": "XAUUSD",
                    "timeframe": "M15",
                    "last_updated": 1640995300,
                    "created_at": 1640995100,
                    "file_size": 512
                }
            ]
        }
        
        sessions = LiveDataSessions(**sessions_data)
        assert len(sessions.sessions) == 2
        assert sessions.sessions[0].symbol == "XAGUSD"
        assert sessions.sessions[1].timeframe == "M15"
    
    def test_websocket_message_valid(self):
        """Test WebSocket message model"""
        message_data = {
            "type": "chart_update",
            "timestamp": "2024-01-01T12:00:00Z",
            "session_id": "session-123",
            "data": {
                "zones": [],
                "ema": []
            }
        }
        
        message = WebSocketMessage(**message_data)
        assert message.type == "chart_update"
        assert message.session_id == "session-123"
        assert "zones" in message.data
    
    def test_websocket_response_valid(self):
        """Test WebSocket response model"""
        response_data = {
            "type": "connection_established",
            "timestamp": "2024-01-01T12:00:00Z",
            "message": "Connected successfully",
            "session_id": "session-123"
        }
        
        response = WebSocketResponse(**response_data)
        assert response.type == "connection_established"
        assert response.message == "Connected successfully"
        assert response.session_id == "session-123"
    
    def test_api_response_valid(self):
        """Test API response model"""
        response_data = {
            "ok": True,
            "message": "Operation completed successfully",
            "data": {
                "job_id": "job-123",
                "status": "running"
            }
        }
        
        response = APIResponse(**response_data)
        assert response.ok is True
        assert "successfully" in response.message
        assert response.data["job_id"] == "job-123"
    
    def test_error_response_valid(self):
        """Test error response model"""
        error_data = {
            "error": "Validation failed",
            "details": {
                "field": "symbols",
                "message": "Field is required"
            }
        }
        
        error = ErrorResponse(**error_data)
        assert error.error == "Validation failed"
        assert error.details["field"] == "symbols"


class TestEnums:
    """Test enum definitions"""
    
    def test_field_type_enum(self):
        """Test FieldType enum"""
        assert FieldType.STR == "str"
        assert FieldType.INT == "int"
        assert FieldType.FLOAT == "float"
        assert FieldType.BOOL == "bool"
        assert FieldType.DATETIME == "datetime"
        assert FieldType.CHOICE == "choice"
        assert FieldType.HIDDEN == "hidden"
    
    def test_destination_enum(self):
        """Test Destination enum"""
        assert Destination.BACKTEST == "backtest"
        assert Destination.ENV == "env"
        assert Destination.META == "meta"


class TestSchemaEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_backtest_request_datetime_validation(self):
        """Test datetime validation in backtest request"""
        # Valid datetime
        request_data = {
            "strategy": "break_retest",
            "symbols": "XAGUSD",
            "timeframe": "H1",
            "start_date": datetime.now(timezone.utc),
            "end_date": datetime.now(timezone.utc),
            "RR": 2.0,
            "INITIAL_EQUITY": 10000.0,
            "RISK_PER_TRADE": 0.02,
            "BREAKOUT_LOOKBACK_PERIOD": 20,
            "ZONE_INVERSION_MARGIN_ATR": 0.5,
            "BREAKOUT_MIN_STRENGTH_ATR": 1.0,
            "MIN_RISK_DISTANCE_ATR": 1.0,
            "SR_CANCELLATION_THRESHOLD_ATR": 0.5,
            "SL_BUFFER_ATR": 0.2,
            "EMA_LENGTH": 20,
            "MODE": "backtest",
            "MARKET_TYPE": "forex"
        }
        
        request = BacktestRequest(**request_data)
        assert request.start_date is not None
        assert request.end_date is not None
    
    def test_symbols_with_spaces(self):
        """Test symbols string with extra spaces"""
        request_data = {
            "strategy": "break_retest",
            "symbols": " XAGUSD , XAUUSD , EURUSD ",
            "timeframe": "H1",
            "start_date": datetime.now(timezone.utc),
            "end_date": datetime.now(timezone.utc),
            "RR": 2.0,
            "INITIAL_EQUITY": 10000.0,
            "RISK_PER_TRADE": 0.02,
            "BREAKOUT_LOOKBACK_PERIOD": 20,
            "ZONE_INVERSION_MARGIN_ATR": 0.5,
            "BREAKOUT_MIN_STRENGTH_ATR": 1.0,
            "MIN_RISK_DISTANCE_ATR": 1.0,
            "SR_CANCELLATION_THRESHOLD_ATR": 0.5,
            "SL_BUFFER_ATR": 0.2,
            "EMA_LENGTH": 20,
            "MODE": "backtest",
            "MARKET_TYPE": "forex"
        }
        
        request = BacktestRequest(**request_data)
        assert request.symbols == ["XAGUSD", "XAUUSD", "EURUSD"]
    
    def test_numeric_field_boundaries(self):
        """Test numeric field boundaries"""
        request_data = {
            "strategy": "break_retest",
            "symbols": "XAGUSD",
            "timeframe": "H1",
            "start_date": datetime.now(timezone.utc),
            "end_date": datetime.now(timezone.utc),
            "RR": 0.1,  # Minimum reasonable RR
            "INITIAL_EQUITY": 1.0,  # Minimum equity
            "RISK_PER_TRADE": 0.001,  # Minimum risk
            "BREAKOUT_LOOKBACK_PERIOD": 1,  # Minimum period
            "ZONE_INVERSION_MARGIN_ATR": 0.0,  # Minimum margin
            "BREAKOUT_MIN_STRENGTH_ATR": 0.1,  # Minimum strength
            "MIN_RISK_DISTANCE_ATR": 0.1,  # Minimum distance
            "SR_CANCELLATION_THRESHOLD_ATR": 0.0,  # Minimum threshold
            "SL_BUFFER_ATR": 0.0,  # Minimum buffer
            "EMA_LENGTH": 1,  # Minimum EMA length
            "MODE": "backtest",
            "MARKET_TYPE": "forex"
        }
        
        request = BacktestRequest(**request_data)
        assert request.RR == 0.1
        assert request.INITIAL_EQUITY == 1.0
        assert request.RISK_PER_TRADE == 0.001
        assert request.BREAKOUT_LOOKBACK_PERIOD == 1
        assert request.EMA_LENGTH == 1
    
    def test_large_numeric_values(self):
        """Test large numeric values"""
        request_data = {
            "strategy": "break_retest",
            "symbols": "XAGUSD",
            "timeframe": "H1",
            "start_date": datetime.now(timezone.utc),
            "end_date": datetime.now(timezone.utc),
            "RR": 1000.0,
            "INITIAL_EQUITY": 1000000.0,
            "RISK_PER_TRADE": 1.0,  # 100% risk (edge case)
            "BREAKOUT_LOOKBACK_PERIOD": 1000,
            "ZONE_INVERSION_MARGIN_ATR": 100.0,
            "BREAKOUT_MIN_STRENGTH_ATR": 100.0,
            "MIN_RISK_DISTANCE_ATR": 100.0,
            "SR_CANCELLATION_THRESHOLD_ATR": 100.0,
            "SL_BUFFER_ATR": 100.0,
            "EMA_LENGTH": 1000,
            "max_candles": 1000000,
            "MODE": "backtest",
            "MARKET_TYPE": "forex"
        }
        
        request = BacktestRequest(**request_data)
        assert request.RR == 1000.0
        assert request.INITIAL_EQUITY == 1000000.0
        assert request.max_candles == 1000000
        assert request.EMA_LENGTH == 1000
