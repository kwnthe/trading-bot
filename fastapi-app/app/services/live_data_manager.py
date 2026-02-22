import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import shutil

from app.core.config import settings


class LiveDataManager:
    """Manages live trading data storage and retrieval"""
    
    def __init__(self, symbol: str, timeframe: str, uuid_str: Optional[str] = None):
        self.symbol = symbol
        self.timeframe = timeframe
        self.uuid = uuid_str or str(uuid.uuid4())
        
        # Set up file paths
        self.session_dir = settings.LIVE_DIR / self.uuid
        self.data_file = self.session_dir / "data.json"
        
        # Initialize data structure
        self.data = {
            "metadata": {
                "symbol": symbol,
                "timeframe": timeframe,
                "created_at": int(datetime.now(timezone.utc).timestamp()),
                "last_updated": int(datetime.now(timezone.utc).timestamp()),
                "uuid": self.uuid
            },
            "candles": [],
            "zones": {
                "supportSegments": [],
                "resistanceSegments": []
            },
            "ema": [],
            "chart_data": {
                "markers": {
                    "points": []
                }
            },
            "extensions": {
                "breakouts": [],
                "events": [],
                "custom_indicators": {}
            }
        }
    
    def load(self) -> None:
        """Load existing data from file"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    loaded_data = json.load(f)
                    # Merge with structure to ensure all fields exist
                    self._merge_data(loaded_data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Failed to load live data: {e}")
    
    def save(self) -> None:
        """Save current data to file"""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Update metadata
        self.data["metadata"]["last_updated"] = int(datetime.now(timezone.utc).timestamp())
        
        # Create backup before saving
        backup_file = self.data_file.with_suffix('.json.bak')
        if self.data_file.exists():
            shutil.copy2(self.data_file, backup_file)
        
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2, default=str)
        except Exception as e:
            # Restore backup if save failed
            if backup_file.exists():
                shutil.copy2(backup_file, self.data_file)
            raise e
    
    def _merge_data(self, loaded_data: Dict[str, Any]) -> None:
        """Merge loaded data with current structure"""
        def merge_dict(target: Dict, source: Dict):
            for key, value in source.items():
                if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                    merge_dict(target[key], value)
                else:
                    target[key] = value
        
        merge_dict(self.data, loaded_data)
    
    def add_candle(self, time: int, open_price: float, high: float, 
                   low: float, close: float, volume: int = 0) -> None:
        """Add a new candle to the data"""
        candle = {
            "time": time,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume
        }
        
        self.data["candles"].append(candle)
        
        # Keep only last 1000 candles to manage file size
        if len(self.data["candles"]) > 1000:
            self.data["candles"] = self.data["candles"][-1000:]
    
    def add_zone(self, zone_type: str, start_time: int, end_time: int, 
                 price: float, strength: float = 1.0) -> None:
        """Add a support or resistance zone"""
        zone = {
            "start": start_time,
            "end": end_time,
            "price": price,
            "strength": strength
        }
        
        if zone_type.lower() == "support":
            self.data["zones"]["supportSegments"].append(zone)
        elif zone_type.lower() == "resistance":
            self.data["zones"]["resistanceSegments"].append(zone)
    
    def add_ema_point(self, time: int, value: float) -> None:
        """Add an EMA data point"""
        ema_point = {
            "time": time,
            "value": value
        }
        
        self.data["ema"].append(ema_point)
        
        # Keep only last 500 EMA points
        if len(self.data["ema"]) > 500:
            self.data["ema"] = self.data["ema"][-500:]
    
    def add_marker(self, time: Union[int, float], value: Union[int, float], 
                   marker_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a chart marker"""
        marker = {
            "time": int(time),
            "value": float(value),
            "marker_type": marker_type,
            "metadata": metadata or {}
        }
        
        self.data["chart_data"]["markers"]["points"].append(marker)
        
        # Keep only last 100 markers
        if len(self.data["chart_data"]["markers"]["points"]) > 100:
            self.data["chart_data"]["markers"]["points"] = self.data["chart_data"]["markers"]["points"][-100:]
    
    def add_breakout(self, time: int, price: float, direction: str, 
                     strength: float = 1.0, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a breakout event"""
        breakout = {
            "time": time,
            "price": price,
            "direction": direction,  # "up" or "down"
            "strength": strength,
            "metadata": metadata or {}
        }
        
        self.data["extensions"]["breakouts"].append(breakout)
    
    def add_event(self, time: int, event_type: str, data: Dict[str, Any]) -> None:
        """Add a custom event"""
        event = {
            "time": time,
            "type": event_type,
            "data": data
        }
        
        self.data["extensions"]["events"].append(event)
    
    def set_custom_indicator(self, indicator_name: str, data: List[Dict[str, Any]]) -> None:
        """Set custom indicator data"""
        self.data["extensions"]["custom_indicators"][indicator_name] = data
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the current data"""
        return {
            "uuid": self.uuid,
            "symbol": self.data["metadata"]["symbol"],
            "timeframe": self.data["metadata"]["timeframe"],
            "last_updated": self.data["metadata"]["last_updated"],
            "candles_count": len(self.data["candles"]),
            "support_zones_count": len(self.data["zones"]["supportSegments"]),
            "resistance_zones_count": len(self.data["zones"]["resistanceSegments"]),
            "ema_points_count": len(self.data["ema"]),
            "markers_count": len(self.data["chart_data"]["markers"]["points"]),
            "breakouts_count": len(self.data["extensions"]["breakouts"]),
            "events_count": len(self.data["extensions"]["events"]),
            "custom_indicators": list(self.data["extensions"]["custom_indicators"].keys()),
            "file_size": self.data_file.stat().st_size if self.data_file.exists() else 0
        }
    
    def cleanup_old_data(self, max_age_hours: int = 24) -> int:
        """Remove old data points to manage file size"""
        cutoff_time = int(datetime.now(timezone.utc).timestamp()) - (max_age_hours * 3600)
        removed_count = 0
        
        # Clean old candles
        original_candle_count = len(self.data["candles"])
        self.data["candles"] = [c for c in self.data["candles"] if c["time"] > cutoff_time]
        removed_count += original_candle_count - len(self.data["candles"])
        
        # Clean old EMA points
        original_ema_count = len(self.data["ema"])
        self.data["ema"] = [e for e in self.data["ema"] if e["time"] > cutoff_time]
        removed_count += original_ema_count - len(self.data["ema"])
        
        # Clean old breakouts and events
        original_breakouts_count = len(self.data["extensions"]["breakouts"])
        self.data["extensions"]["breakouts"] = [b for b in self.data["extensions"]["breakouts"] if b["time"] > cutoff_time]
        removed_count += original_breakouts_count - len(self.data["extensions"]["breakouts"])
        
        original_events_count = len(self.data["extensions"]["events"])
        self.data["extensions"]["events"] = [e for e in self.data["extensions"]["events"] if e["time"] > cutoff_time]
        removed_count += original_events_count - len(self.data["extensions"]["events"])
        
        # Save after cleanup
        if removed_count > 0:
            self.save()
        
        return removed_count


def get_all_live_sessions() -> List[Dict[str, Any]]:
    """Get all live data sessions"""
    sessions = []
    
    for session_dir in settings.LIVE_DIR.iterdir():
        if session_dir.is_dir():
            data_file = session_dir / "data.json"
            if data_file.exists():
                try:
                    with open(data_file, 'r') as f:
                        data = json.load(f)
                    
                    metadata = data.get("metadata", {})
                    session_info = {
                        "uuid": session_dir.name,
                        "symbol": metadata.get("symbol", "Unknown"),
                        "timeframe": metadata.get("timeframe", "Unknown"),
                        "last_updated": metadata.get("last_updated", 0),
                        "created_at": metadata.get("created_at", 0),
                        "file_size": data_file.stat().st_size
                    }
                    sessions.append(session_info)
                except Exception as e:
                    print(f"Failed to read session {session_dir.name}: {e}")
                    continue
    
    # Sort by last_updated (most recent first)
    sessions.sort(key=lambda x: x["last_updated"], reverse=True)
    return sessions


def get_live_data_manager(uuid_str: str) -> Optional[LiveDataManager]:
    """Get LiveDataManager for a specific UUID"""
    data_file = settings.LIVE_DIR / uuid_str / "data.json"
    
    if not data_file.exists():
        return None
    
    # Try to read symbol and timeframe from existing data
    try:
        with open(data_file, 'r') as f:
            data = json.load(f)
        
        metadata = data.get("metadata", {})
        symbol = metadata.get("symbol", "Unknown")
        timeframe = metadata.get("timeframe", "H1")
        
        manager = LiveDataManager(symbol, timeframe, uuid_str)
        manager.load()
        return manager
    except Exception:
        return None
