import pytest
import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.models.schemas import BacktestRequest, LiveTradingRequest
from app.services.presets_store import load_presets
from tests.conftest import TestDataManager


class TestParamsAPI:
    """Test parameter-related API endpoints"""
    
    def test_get_params(self, client):
        """Test getting parameter definitions"""
        response = client.get("/api/params")
        assert response.status_code == 200
        
        data = response.json()
        assert "param_defs" in data
        assert "initial" in data
        assert len(data["param_defs"]) > 0
        
        # Check structure of parameter definitions
        param_def = data["param_defs"][0]
        assert "name" in param_def
        assert "label" in param_def
        assert "field_type" in param_def
        assert "destination" in param_def
        assert "required" in param_def
        assert "group" in param_def
    
    def test_get_strategies(self, client):
        """Test getting available strategies"""
        response = client.get("/api/strategies")
        assert response.status_code == 200
        
        data = response.json()
        assert "strategies" in data
        assert len(data["strategies"]) > 0
        
        # Check structure of strategy
        strategy = data["strategies"][0]
        assert "id" in strategy
        assert "label" in strategy


class TestBacktestAPI:
    """Test backtest-related API endpoints"""
    
    def test_run_backtest(self, client, test_settings):
        """Test running a backtest"""
        request_data = {
            "strategy": "break_retest",
            "symbols": "XAGUSD",
            "timeframe": "H1",
            "start_date": datetime.now(timezone.utc).isoformat(),
            "end_date": datetime.now(timezone.utc).isoformat(),
            "spread_pips": 0.0,
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
            "MODE": "backtest",
            "MARKET_TYPE": "forex"
        }
        
        response = client.post("/api/run", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "job_id" in data
        assert "job_url" in data
        assert "status_url" in data
        assert "result_url" in data
        
        # Verify job was created
        job_id = data["job_id"]
        job_dir = test_settings.JOBS_DIR / job_id
        assert job_dir.exists()
        assert (job_dir / "params.json").exists()
        assert (job_dir / "status.json").exists()
    
    def test_run_backtest_invalid_data(self, client):
        """Test running backtest with invalid data"""
        # Missing required fields
        request_data = {
            "strategy": "break_retest",
            "symbols": "",  # Empty symbols should fail
        }
        
        response = client.post("/api/run", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_get_job_status(self, client, sample_job, test_settings):
        """Test getting job status"""
        job_id = sample_job["job_id"]
        
        # Create status file
        TestDataManager.create_job_status_file(sample_job["paths"], "running")
        
        response = client.get(f"/api/jobs/{job_id}/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "running"
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_get_job_status_not_found(self, client):
        """Test getting status for non-existent job"""
        response = client.get("/api/jobs/nonexistent/status")
        assert response.status_code == 404
    
    def test_get_job_result(self, client, sample_job):
        """Test getting job result"""
        job_id = sample_job["job_id"]
        
        # Create result file
        TestDataManager.create_result_file(sample_job["paths"])
        
        response = client.get(f"/api/jobs/{job_id}/result")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "result" in data
        assert "completed_at" in data
    
    def test_get_job_result_not_ready(self, client, sample_job):
        """Test getting result when not ready"""
        job_id = sample_job["job_id"]
        
        response = client.get(f"/api/jobs/{job_id}/result")
        assert response.status_code == 404


class TestLiveTradingAPI:
    """Test live trading-related API endpoints"""
    
    def test_get_active_session(self, client, test_settings):
        """Test getting active live session"""
        response = client.get("/api/live/active")
        assert response.status_code == 200
        
        data = response.json()
        assert "active_session_id" in data
        # Should be None initially
        assert data["active_session_id"] is None
    
    def test_start_live_session(self, client, test_settings):
        """Test starting a live trading session"""
        request_data = {
            "strategy": "break_retest",
            "symbols": "XAGUSD",
            "timeframe": "H1",
            "RR": 2.0,
            "INITIAL_EQUITY": 10000.0,
            "RISK_PER_TRADE": 0.02
        }
        
        response = client.post("/api/live/run", data=json.dumps(request_data))
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "session_id" in data
        assert "status_url" in data
        assert "snapshot_url" in data
        assert "stop_url" in data
        
        # Verify session was created
        session_id = data["session_id"]
        session_dir = test_settings.LIVE_DIR / session_id
        assert session_dir.exists()
        assert (session_dir / "params.json").exists()
        assert (session_dir / "status.json").exists()
    
    def test_start_live_session_conflict(self, client, sample_live_session, test_settings):
        """Test starting live session when one is already running"""
        # Set up existing active session
        from app.services.live_store import set_active_session_id
        set_active_session_id(test_settings.BASE_DIR, sample_live_session["session_id"])
        
        # Create running status
        TestDataManager.create_live_status_file(sample_live_session["paths"], "running")
        
        request_data = {
            "strategy": "break_retest",
            "symbols": "XAGUSD",
            "timeframe": "H1"
        }
        
        response = client.post("/api/live/run", data=json.dumps(request_data))
        assert response.status_code == 409  # Conflict
    
    def test_get_live_session_status(self, client, sample_live_session):
        """Test getting live session status"""
        session_id = sample_live_session["session_id"]
        
        # Create status file
        TestDataManager.create_live_status_file(sample_live_session["paths"], "running")
        
        response = client.get(f"/api/live/{session_id}/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data["session_id"] == session_id
        assert data["state"] == "running"
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_get_live_session_status_not_found(self, client):
        """Test getting status for non-existent session"""
        response = client.get("/api/live/nonexistent/status")
        assert response.status_code == 404
    
    def test_get_live_session_snapshot(self, client, sample_live_session):
        """Test getting live session snapshot"""
        session_id = sample_live_session["session_id"]
        
        # Create snapshot file
        TestDataManager.create_snapshot_file(sample_live_session["paths"])
        
        response = client.get(f"/api/live/{session_id}/snapshot")
        assert response.status_code == 200
        
        data = response.json()
        assert "timestamp" in data
        assert "data" in data
    
    def test_get_live_session_snapshot_not_ready(self, client, sample_live_session):
        """Test getting snapshot when not ready"""
        session_id = sample_live_session["session_id"]
        
        response = client.get(f"/api/live/{session_id}/snapshot")
        assert response.status_code == 404
    
    def test_stop_live_session(self, client, sample_live_session):
        """Test stopping a live trading session"""
        session_id = sample_live_session["session_id"]
        
        # Create status file with PID
        TestDataManager.create_live_status_file(sample_live_session["paths"], "running")
        
        response = client.post(f"/api/live/{session_id}/stop")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "killed" in data


class TestLiveDataAPI:
    """Test live data API endpoints"""
    
    def test_get_live_data(self, client, sample_live_data):
        """Test getting live data"""
        uuid = sample_live_data.uuid
        
        response = client.get(f"/api/live/{uuid}/data")
        assert response.status_code == 200
        
        data = response.json()
        assert "metadata" in data
        assert "candles" in data
        assert "zones" in data
        assert "ema" in data
        assert "chart_data" in data
        assert "extensions" in data
        
        # Check data structure
        assert len(data["candles"]) > 0
        assert len(data["zones"]["supportSegments"]) > 0
        assert len(data["zones"]["resistanceSegments"]) > 0
        assert len(data["ema"]) > 0
        assert len(data["chart_data"]["markers"]["points"]) > 0
    
    def test_get_live_data_not_found(self, client):
        """Test getting live data for non-existent UUID"""
        response = client.get("/api/live/nonexistent/data")
        assert response.status_code == 404
    
    def test_get_live_data_summary(self, client, sample_live_data):
        """Test getting live data summary"""
        uuid = sample_live_data.uuid
        
        response = client.get(f"/api/live/{uuid}/summary")
        assert response.status_code == 200
        
        data = response.json()
        assert data["uuid"] == uuid
        assert data["symbol"] == "XAGUSD"
        assert data["timeframe"] == "H1"
        assert data["candles_count"] > 0
        assert data["support_zones_count"] > 0
        assert data["resistance_zones_count"] > 0
        assert data["ema_points_count"] > 0
        assert data["markers_count"] > 0
    
    def test_get_live_data_sessions(self, client, sample_live_data):
        """Test listing all live data sessions"""
        response = client.get("/api/live/sessions")
        assert response.status_code == 200
        
        data = response.json()
        assert "sessions" in data
        assert len(data["sessions"]) > 0
        
        # Check session structure
        session = data["sessions"][0]
        assert "uuid" in session
        assert "symbol" in session
        assert "timeframe" in session
        assert "last_updated" in session
        assert "created_at" in session
        assert "file_size" in session
    
    def test_add_marker(self, client, sample_live_data):
        """Test adding a marker to live data"""
        uuid = sample_live_data.uuid
        
        marker_data = {
            "time": 1640995200,
            "value": 22.5,
            "marker_type": "test",
            "metadata": {"note": "Test marker"}
        }
        
        response = client.post(f"/api/live/{uuid}/add_marker", json=marker_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "successfully" in data["message"]
    
    def test_add_marker_invalid_data(self, client, sample_live_data):
        """Test adding marker with invalid data"""
        uuid = sample_live_data.uuid
        
        # Missing required fields
        marker_data = {
            "time": 1640995200,
            # Missing value and marker_type
        }
        
        response = client.post(f"/api/live/{uuid}/add_marker", json=marker_data)
        assert response.status_code == 422  # Validation error
    
    def test_cleanup_old_data(self, client, sample_live_data):
        """Test cleaning up old data"""
        uuid = sample_live_data.uuid
        
        response = client.post(f"/api/live/{uuid}/cleanup")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "completed" in data["message"]


class TestPresetsAPI:
    """Test preset-related API endpoints"""
    
    def test_list_presets(self, client, sample_preset):
        """Test listing all presets"""
        response = client.get("/api/presets")
        assert response.status_code == 200
        
        data = response.json()
        assert "presets" in data
        assert len(data["presets"]) > 0
        assert sample_preset["name"] in data["presets"]
    
    def test_save_preset(self, client, test_settings):
        """Test saving a preset"""
        preset_data = {
            "name": "new_test_preset",
            "values": {
                "symbols": "EURUSD",
                "timeframe": "M15",
                "RR": 3.0,
                "INITIAL_EQUITY": 5000
            }
        }
        
        response = client.post("/api/presets", json=preset_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "successfully" in data["message"]
        
        # Verify preset was saved
        presets = load_presets(test_settings.BASE_DIR)
        assert "new_test_preset" in presets
    
    def test_save_preset_invalid_name(self, client):
        """Test saving preset with invalid name"""
        preset_data = {
            "name": "",  # Empty name should fail
            "values": {"symbols": "EURUSD"}
        }
        
        response = client.post("/api/presets", json=preset_data)
        assert response.status_code == 400  # Bad request
    
    def test_get_preset(self, client, sample_preset):
        """Test getting a specific preset"""
        preset_name = sample_preset["name"]
        
        response = client.get(f"/api/presets/{preset_name}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == preset_name
        assert "values" in data
        assert data["values"]["symbols"] == "XAGUSD,XAUUSD"
    
    def test_get_preset_not_found(self, client):
        """Test getting non-existent preset"""
        response = client.get("/api/presets/nonexistent")
        assert response.status_code == 404
    
    def test_delete_preset(self, client, sample_preset, test_settings):
        """Test deleting a preset"""
        preset_name = sample_preset["name"]
        
        response = client.delete(f"/api/presets/{preset_name}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        assert "successfully" in data["message"]
        
        # Verify preset was deleted
        presets = load_presets(test_settings.BASE_DIR)
        assert preset_name not in presets
    
    def test_delete_preset_not_found(self, client):
        """Test deleting non-existent preset"""
        response = client.delete("/api/presets/nonexistent")
        assert response.status_code == 404


class TestHealthEndpoints:
    """Test health and general endpoints"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "version" in data
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
