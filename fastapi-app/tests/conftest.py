import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from fastapi.testclient import TestClient
import json
import uuid

from main import app
from app.core.config import settings
from app.services.job_store import create_job, JobPaths
from app.services.live_store import create_live_session, LivePaths
from app.services.presets_store import upsert_preset, load_presets


@pytest.fixture
def client():
    """Test client for FastAPI app"""
    return TestClient(app)


@pytest.fixture
def temp_dir():
    """Temporary directory for test files"""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_settings(temp_dir):
    """Test settings with temporary directories"""
    # Override settings for testing
    original_base_dir = settings.BASE_DIR
    original_var_dir = settings.VAR_DIR
    original_jobs_dir = settings.JOBS_DIR
    original_live_dir = settings.LIVE_DIR
    
    # Set up test directories
    settings.BASE_DIR = temp_dir
    settings.VAR_DIR = temp_dir / "var"
    settings.JOBS_DIR = temp_dir / "var" / "jobs"
    settings.LIVE_DIR = temp_dir / "var" / "live"
    
    # Create directories
    settings.VAR_DIR.mkdir(exist_ok=True)
    settings.JOBS_DIR.mkdir(exist_ok=True)
    settings.LIVE_DIR.mkdir(exist_ok=True)
    
    yield settings
    
    # Restore original settings
    settings.BASE_DIR = original_base_dir
    settings.VAR_DIR = original_var_dir
    settings.JOBS_DIR = original_jobs_dir
    settings.LIVE_DIR = original_live_dir


@pytest.fixture
def sample_job(test_settings):
    """Create a sample job for testing"""
    params = {
        "backtest_args": {
            "symbols": ["XAGUSD"],
            "timeframe": "H1",
            "start_date": datetime.now(timezone.utc).isoformat(),
            "end_date": datetime.now(timezone.utc).isoformat(),
        },
        "env_overrides": {"RR": "2.0", "INITIAL_EQUITY": "10000"},
        "meta": {"MODE": "backtest"}
    }
    
    job_id, paths = create_job(test_settings.BASE_DIR, params)
    return {"job_id": job_id, "paths": paths, "params": params}


@pytest.fixture
def sample_live_session(test_settings):
    """Create a sample live session for testing"""
    params = {
        "strategy": "break_retest",
        "backtest_args": {
            "symbols": ["XAGUSD"],
            "timeframe": "H1",
        },
        "env_overrides": {"RR": "2.0", "INITIAL_EQUITY": "10000"},
        "meta": {"MODE": "live"}
    }
    
    session_id, paths = create_live_session(test_settings.BASE_DIR, params)
    return {"session_id": session_id, "paths": paths, "params": params}


@pytest.fixture
def sample_preset(test_settings):
    """Create a sample preset for testing"""
    preset_name = "test_preset"
    preset_values = {
        "symbols": "XAGUSD,XAUUSD",
        "timeframe": "H1",
        "RR": 2.0,
        "INITIAL_EQUITY": 10000,
        "RISK_PER_TRADE": 0.02
    }
    
    upsert_preset(test_settings.BASE_DIR, preset_name, preset_values)
    return {"name": preset_name, "values": preset_values}


@pytest.fixture
def sample_live_data(test_settings):
    """Create sample live data for testing"""
    from app.services.live_data_manager import LiveDataManager
    
    manager = LiveDataManager("XAGUSD", "H1", str(uuid.uuid4()))
    
    # Add sample data
    manager.add_candle(1640995200, 22.5, 22.8, 22.3, 22.7, 1000)
    manager.add_candle(1640998800, 22.7, 23.0, 22.6, 22.9, 1200)
    
    manager.add_zone("support", 1640995200, 1640998800, 22.3, 1.0)
    manager.add_zone("resistance", 1640995200, 1640998800, 23.0, 1.0)
    
    manager.add_ema_point(1640995200, 22.6)
    manager.add_ema_point(1640998800, 22.8)
    
    manager.add_marker(1640995200, 22.3, "support", {"note": "Test support"})
    manager.add_marker(1640998800, 23.0, "resistance", {"note": "Test resistance"})
    
    manager.save()
    
    return manager


@pytest.fixture
def mock_websocket():
    """Mock WebSocket for testing"""
    from unittest.mock import Mock
    from fastapi import WebSocket
    
    websocket = Mock(spec=WebSocket)
    websocket.accept = Mock()
    websocket.send_text = Mock()
    websocket.receive_text = Mock()
    websocket.close = Mock()
    
    return websocket


class TestDataManager:
    """Helper class for managing test data"""
    
    @staticmethod
    def create_job_status_file(paths: JobPaths, status: str = "queued"):
        """Create a job status file"""
        status_data = {
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        with open(paths.status_json, 'w') as f:
            json.dump(status_data, f, indent=2)
    
    @staticmethod
    def create_live_status_file(paths: LivePaths, state: str = "queued"):
        """Create a live session status file"""
        status_data = {
            "state": state,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        with open(paths.status_json, 'w') as f:
            json.dump(status_data, f, indent=2)
    
    @staticmethod
    def create_result_file(paths: JobPaths):
        """Create a result file"""
        result_data = {
            "status": "completed",
            "result": {
                "total_trades": 10,
                "profitable_trades": 6,
                "total_profit": 150.5,
                "max_drawdown": -25.3
            },
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        
        with open(paths.result_json, 'w') as f:
            json.dump(result_data, f, indent=2)
    
    @staticmethod
    def create_snapshot_file(paths: LivePaths):
        """Create a snapshot file"""
        snapshot_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "current_price": 22.75,
                "zones": {
                    "support": [{"price": 22.3, "strength": 1.0}],
                    "resistance": [{"price": 23.0, "strength": 1.0}]
                },
                "ema": [{"time": 1640995200, "value": 22.6}],
                "indicators": {
                    "rsi": 55.2,
                    "macd": {"signal": 0.1, "histogram": 0.05}
                }
            }
        }
        
        with open(paths.snapshot_json, 'w') as f:
            json.dump(snapshot_data, f, indent=2)
