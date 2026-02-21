import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.services.params import get_param_definitions, get_initial_form_data, get_strategies
from app.services.job_store import create_job, read_status, write_status, is_pid_running, tail_text_file
from app.services.live_store import create_live_session, read_live_status, write_live_status, get_active_session_id, set_active_session_id
from app.services.presets_store import upsert_preset, load_presets, delete_preset, normalize_preset_name
from app.services.live_data_manager import LiveDataManager, get_all_live_sessions, get_live_data_manager


class TestParamsService:
    """Test parameter service functions"""
    
    def test_get_param_definitions(self):
        """Test getting parameter definitions"""
        defs = get_param_definitions()
        
        assert isinstance(defs, list)
        assert len(defs) > 0
        
        # Check structure of parameter definition
        param_def = defs[0]
        assert "name" in param_def
        assert "label" in param_def
        assert "field_type" in param_def
        assert "destination" in param_def
        assert "required" in param_def
        assert "group" in param_def
        assert "help_text" in param_def
        assert "choices" in param_def
    
    def test_get_initial_form_data(self):
        """Test getting initial form data"""
        initial = get_initial_form_data()
        
        assert isinstance(initial, dict)
        # Should contain default values for parameters with fallback defaults
        assert "symbols" in initial
        assert "timeframe" in initial
        assert "MODE" in initial
        assert "MARKET_TYPE" in initial
    
    def test_get_strategies(self):
        """Test getting strategies"""
        strategies = get_strategies()
        
        assert isinstance(strategies, list)
        assert len(strategies) > 0
        
        # Check structure of strategy
        strategy = strategies[0]
        assert "id" in strategy
        assert "label" in strategy


class TestJobStoreService:
    """Test job store service functions"""
    
    def test_create_job(self, test_settings):
        """Test creating a job"""
        params = {
            "backtest_args": {"symbols": ["XAGUSD"], "timeframe": "H1"},
            "env_overrides": {"RR": "2.0"},
            "meta": {"MODE": "backtest"}
        }
        
        job_id, paths = create_job(test_settings.BASE_DIR, params)
        
        # Verify job was created
        assert job_id is not None
        assert isinstance(job_id, str)
        
        # Verify paths
        assert paths.job_dir.exists()
        assert paths.params_json.exists()
        assert paths.status_json.exists()
        
        # Verify parameter file content
        with open(paths.params_json, 'r') as f:
            saved_params = json.load(f)
        assert saved_params == params
        
        # Verify initial status
        status = read_status(paths)
        assert status["status"] == "queued"
        assert "created_at" in status
        assert "updated_at" in status
    
    def test_read_status(self, sample_job):
        """Test reading job status"""
        paths = sample_job["paths"]
        
        # Read existing status
        status = read_status(paths)
        assert status["status"] == "queued"
        
        # Test with non-existent file
        non_existent_paths = sample_job["paths"]
        non_existent_paths.status_json = Path("/non/existent/status.json")
        status = read_status(non_existent_paths)
        assert status["status"] == "unknown"
        assert "error" in status
    
    def test_write_status(self, sample_job):
        """Test writing job status"""
        paths = sample_job["paths"]
        
        # Write status update
        update = {"status": "running", "pid": 12345}
        write_status(paths, update)
        
        # Verify update
        status = read_status(paths)
        assert status["status"] == "running"
        assert status["pid"] == 12345
        assert "updated_at" in status
    
    def test_is_pid_running(self):
        """Test PID running check"""
        # Test with current process PID (should be running)
        import os
        current_pid = os.getpid()
        assert is_pid_running(current_pid) is True
        
        # Test with non-existent PID
        assert is_pid_running(99999) is False
    
    def test_tail_text_file(self, sample_job):
        """Test tailing text file"""
        paths = sample_job["paths"]
        
        # Create test log file
        test_lines = [f"Line {i}\n" for i in range(1, 26)]
        with open(paths.stdout_log, 'w') as f:
            f.writelines(test_lines)
        
        # Test tail
        tail_content = tail_text_file(paths.stdout_log, num_lines=10)
        lines = tail_content.split('\n')
        
        # Should get last 10 lines (plus empty line at end)
        assert len([line for line in lines if line.strip()]) == 10
        assert "Line 25" in tail_content
        assert "Line 16" in tail_content
        assert "Line 15" not in tail_content
        
        # Test with non-existent file
        non_existent_file = Path("/non/existent.log")
        tail_content = tail_text_file(non_existent_file)
        assert tail_content == ""


class TestLiveStoreService:
    """Test live store service functions"""
    
    def test_create_live_session(self, test_settings):
        """Test creating a live session"""
        params = {
            "strategy": "break_retest",
            "backtest_args": {"symbols": ["XAGUSD"], "timeframe": "H1"},
            "env_overrides": {"RR": "2.0"},
            "meta": {"MODE": "live"}
        }
        
        session_id, paths = create_live_session(test_settings.BASE_DIR, params)
        
        # Verify session was created
        assert session_id is not None
        assert isinstance(session_id, str)
        
        # Verify paths
        assert paths.session_dir.exists()
        assert paths.params_json.exists()
        assert paths.status_json.exists()
        
        # Verify parameter file content
        with open(paths.params_json, 'r') as f:
            saved_params = json.load(f)
        assert saved_params == params
        
        # Verify initial status
        status = read_live_status(paths)
        assert status["state"] == "queued"
        assert "created_at" in status
        assert "updated_at" in status
    
    def test_read_live_status(self, sample_live_session):
        """Test reading live session status"""
        paths = sample_live_session["paths"]
        
        # Read existing status
        status = read_live_status(paths)
        assert status["state"] == "queued"
        
        # Test with non-existent file
        non_existent_paths = sample_live_session["paths"]
        non_existent_paths.status_json = Path("/non/existent/status.json")
        status = read_live_status(non_existent_paths)
        assert status["state"] == "unknown"
        assert "error" in status
    
    def test_write_live_status(self, sample_live_session):
        """Test writing live session status"""
        paths = sample_live_session["paths"]
        
        # Write status update
        update = {"state": "running", "pid": 12345}
        write_live_status(paths, update)
        
        # Verify update
        status = read_live_status(paths)
        assert status["state"] == "running"
        assert status["pid"] == 12345
        assert "updated_at" in status
    
    def test_active_session_management(self, test_settings):
        """Test active session ID management"""
        # Initially no active session
        active = get_active_session_id(test_settings.BASE_DIR)
        assert active is None
        
        # Set active session
        session_id = "test_session_123"
        set_active_session_id(test_settings.BASE_DIR, session_id)
        
        # Verify active session
        active = get_active_session_id(test_settings.BASE_DIR)
        assert active == session_id
        
        # Clear active session
        set_active_session_id(test_settings.BASE_DIR, None)
        
        # Verify no active session
        active = get_active_session_id(test_settings.BASE_DIR)
        assert active is None
    
    def test_tail_live_text_file(self, sample_live_session):
        """Test tailing live session log file"""
        paths = sample_live_session["paths"]
        
        # Create test log file
        test_lines = [f"Live Line {i}\n" for i in range(1, 16)]
        with open(paths.stdout_log, 'w') as f:
            f.writelines(test_lines)
        
        # Test tail
        tail_content = tail_text_file(paths.stdout_log, num_lines=5)
        lines = tail_content.split('\n')
        
        # Should get last 5 lines (plus empty line at end)
        assert len([line for line in lines if line.strip()]) == 5
        assert "Live Line 15" in tail_content
        assert "Live Line 11" in tail_content
        assert "Live Line 10" not in tail_content


class TestPresetsStoreService:
    """Test presets store service functions"""
    
    def test_normalize_preset_name(self):
        """Test preset name normalization"""
        # Valid names
        assert normalize_preset_name("Test Preset") == "test_preset"
        assert normalize_preset_name("My-Strategy_123") == "my-strategy_123"
        assert normalize_preset_name("  spaced  name  ") == "spaced_name"
        
        # Invalid names
        with pytest.raises(ValueError):
            normalize_preset_name("")
        
        with pytest.raises(ValueError):
            normalize_preset_name("!" * 51)  # Too long
    
    def test_upsert_and_load_presets(self, test_settings):
        """Test saving and loading presets"""
        preset_name = "test_preset"
        preset_values = {
            "symbols": "XAGUSD,XAUUSD",
            "timeframe": "H1",
            "RR": 2.0,
            "INITIAL_EQUITY": 10000
        }
        
        # Save preset
        upsert_preset(test_settings.BASE_DIR, preset_name, preset_values)
        
        # Load presets
        presets = load_presets(test_settings.BASE_DIR)
        
        # Verify preset was saved
        assert preset_name in presets
        assert presets[preset_name] == preset_values
    
    def test_delete_preset(self, test_settings):
        """Test deleting a preset"""
        preset_name = "test_preset_to_delete"
        preset_values = {"symbols": "XAGUSD"}
        
        # Save preset first
        upsert_preset(test_settings.BASE_DIR, preset_name, preset_values)
        presets = load_presets(test_settings.BASE_DIR)
        assert preset_name in presets
        
        # Delete preset
        delete_preset(test_settings.BASE_DIR, preset_name)
        
        # Verify preset was deleted
        presets = load_presets(test_settings.BASE_DIR)
        assert preset_name not in presets
    
    def test_delete_nonexistent_preset(self, test_settings):
        """Test deleting non-existent preset"""
        with pytest.raises(FileNotFoundError):
            delete_preset(test_settings.BASE_DIR, "nonexistent_preset")


class TestLiveDataManagerService:
    """Test live data manager service"""
    
    def test_live_data_manager_creation(self, test_settings):
        """Test creating LiveDataManager"""
        manager = LiveDataManager("XAGUSD", "H1")
        
        assert manager.symbol == "XAGUSD"
        assert manager.timeframe == "H1"
        assert manager.uuid is not None
        assert isinstance(manager.uuid, str)
        
        # Check initial data structure
        assert "metadata" in manager.data
        assert "candles" in manager.data
        assert "zones" in manager.data
        assert "ema" in manager.data
        assert "chart_data" in manager.data
        assert "extensions" in manager.data
    
    def test_add_candle(self, test_settings):
        """Test adding candle data"""
        manager = LiveDataManager("XAGUSD", "H1")
        
        # Add candle
        manager.add_candle(1640995200, 22.5, 22.8, 22.3, 22.7, 1000)
        
        assert len(manager.data["candles"]) == 1
        candle = manager.data["candles"][0]
        assert candle["time"] == 1640995200
        assert candle["open"] == 22.5
        assert candle["high"] == 22.8
        assert candle["low"] == 22.3
        assert candle["close"] == 22.7
        assert candle["volume"] == 1000
    
    def test_add_zone(self, test_settings):
        """Test adding support/resistance zones"""
        manager = LiveDataManager("XAGUSD", "H1")
        
        # Add support zone
        manager.add_zone("support", 1640995200, 1640998800, 22.3, 1.0)
        
        # Add resistance zone
        manager.add_zone("resistance", 1640995200, 1640998800, 23.0, 1.5)
        
        assert len(manager.data["zones"]["supportSegments"]) == 1
        assert len(manager.data["zones"]["resistanceSegments"]) == 1
        
        support = manager.data["zones"]["supportSegments"][0]
        assert support["start"] == 1640995200
        assert support["end"] == 1640998800
        assert support["price"] == 22.3
        assert support["strength"] == 1.0
    
    def test_add_ema_point(self, test_settings):
        """Test adding EMA data points"""
        manager = LiveDataManager("XAGUSD", "H1")
        
        # Add EMA points
        manager.add_ema_point(1640995200, 22.6)
        manager.add_ema_point(1640998800, 22.8)
        
        assert len(manager.data["ema"]) == 2
        
        ema1 = manager.data["ema"][0]
        assert ema1["time"] == 1640995200
        assert ema1["value"] == 22.6
    
    def test_add_marker(self, test_settings):
        """Test adding chart markers"""
        manager = LiveDataManager("XAGUSD", "H1")
        
        # Add marker
        manager.add_marker(1640995200, 22.3, "support", {"note": "Test"})
        
        assert len(manager.data["chart_data"]["markers"]["points"]) == 1
        
        marker = manager.data["chart_data"]["markers"]["points"][0]
        assert marker["time"] == 1640995200
        assert marker["value"] == 22.3
        assert marker["marker_type"] == "support"
        assert marker["metadata"]["note"] == "Test"
    
    def test_add_breakout_and_event(self, test_settings):
        """Test adding breakouts and events"""
        manager = LiveDataManager("XAGUSD", "H1")
        
        # Add breakout
        manager.add_breakout(1640995200, 23.1, "up", 1.2, {"note": "Strong breakout"})
        
        # Add event
        manager.add_event(1640995200, "signal", {"type": "buy", "strength": 0.8})
        
        assert len(manager.data["extensions"]["breakouts"]) == 1
        assert len(manager.data["extensions"]["events"]) == 1
        
        breakout = manager.data["extensions"]["breakouts"][0]
        assert breakout["time"] == 1640995200
        assert breakout["price"] == 23.1
        assert breakout["direction"] == "up"
        
        event = manager.data["extensions"]["events"][0]
        assert event["time"] == 1640995200
        assert event["type"] == "signal"
    
    def test_save_and_load(self, test_settings):
        """Test saving and loading data"""
        manager = LiveDataManager("XAGUSD", "H1")
        
        # Add some data
        manager.add_candle(1640995200, 22.5, 22.8, 22.3, 22.7)
        manager.add_zone("support", 1640995200, 1640998800, 22.3)
        
        # Save data
        manager.save()
        
        # Verify file was created
        assert manager.data_file.exists()
        
        # Create new manager and load data
        new_manager = LiveDataManager("XAGUSD", "H1", manager.uuid)
        new_manager.load()
        
        # Verify data was loaded
        assert len(new_manager.data["candles"]) == 1
        assert len(new_manager.data["zones"]["supportSegments"]) == 1
        assert new_manager.data["metadata"]["symbol"] == "XAGUSD"
        assert new_manager.data["metadata"]["timeframe"] == "H1"
    
    def test_get_summary(self, test_settings):
        """Test getting data summary"""
        manager = LiveDataManager("XAGUSD", "H1")
        
        # Add various data types
        manager.add_candle(1640995200, 22.5, 22.8, 22.3, 22.7)
        manager.add_zone("support", 1640995200, 1640998800, 22.3)
        manager.add_zone("resistance", 1640995200, 1640998800, 23.0)
        manager.add_ema_point(1640995200, 22.6)
        manager.add_marker(1640995200, 22.3, "support")
        manager.add_breakout(1640995200, 23.1, "up")
        manager.add_event(1640995200, "signal", {"type": "buy"})
        
        # Get summary
        summary = manager.get_summary()
        
        # Verify summary structure
        assert summary["uuid"] == manager.uuid
        assert summary["symbol"] == "XAGUSD"
        assert summary["timeframe"] == "H1"
        assert summary["candles_count"] == 1
        assert summary["support_zones_count"] == 1
        assert summary["resistance_zones_count"] == 1
        assert summary["ema_points_count"] == 1
        assert summary["markers_count"] == 1
        assert summary["breakouts_count"] == 1
        assert summary["events_count"] == 1
    
    def test_cleanup_old_data(self, test_settings):
        """Test cleaning up old data"""
        manager = LiveDataManager("XAGUSD", "H1")
        
        # Add data with old timestamps (more than 24 hours ago for testing)
        old_time = int(datetime.now(timezone.utc).timestamp()) - (25 * 3600)  # 25 hours ago
        recent_time = int(datetime.now(timezone.utc).timestamp()) - (1 * 3600)  # 1 hour ago
        
        # Add old data
        manager.add_candle(old_time, 22.5, 22.8, 22.3, 22.7)
        manager.add_ema_point(old_time, 22.6)
        manager.add_breakout(old_time, 23.1, "up")
        manager.add_event(old_time, "signal", {"type": "buy"})
        
        # Add recent data
        manager.add_candle(recent_time, 22.7, 23.0, 22.6, 22.9)
        manager.add_ema_point(recent_time, 22.8)
        
        # Cleanup old data
        removed_count = manager.cleanup_old_data(max_age_hours=24)
        
        # Verify old data was removed, recent data remains
        assert removed_count > 0
        assert len(manager.data["candles"]) == 1  # Only recent candle
        assert len(manager.data["ema"]) == 1  # Only recent EMA
        assert len(manager.data["extensions"]["breakouts"]) == 0  # Old breakout removed
        assert len(manager.data["extensions"]["events"]) == 0  # Old event removed
    
    def test_get_all_live_sessions(self, sample_live_data):
        """Test getting all live sessions"""
        sessions = get_all_live_sessions()
        
        assert isinstance(sessions, list)
        assert len(sessions) > 0
        
        # Check session structure
        session = sessions[0]
        assert "uuid" in session
        assert "symbol" in session
        assert "timeframe" in session
        assert "last_updated" in session
        assert "created_at" in session
        assert "file_size" in session
    
    def test_get_live_data_manager(self, sample_live_data):
        """Test getting LiveDataManager for existing UUID"""
        manager = get_live_data_manager(sample_live_data.uuid)
        
        assert manager is not None
        assert manager.uuid == sample_live_data.uuid
        assert manager.symbol == "XAGUSD"
        assert manager.timeframe == "H1"
        assert len(manager.data["candles"]) > 0
    
    def test_get_live_data_manager_not_found(self):
        """Test getting LiveDataManager for non-existent UUID"""
        manager = get_live_data_manager("nonexistent-uuid")
        assert manager is None
