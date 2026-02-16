#!/usr/bin/env python3
"""
Flexible Live Data Manager for unified JSON storage
Supports easy extension of data types and points
"""
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

class LiveDataManager:
    """
    Manages unified JSON data storage for live trading
    Identical structure to existing live runner output but with flexible extensions
    """
    
    def __init__(self, symbol: str, timeframe: str = "H1"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.uuid = str(uuid.uuid4())
        self.data_dir = Path(__file__).resolve().parent.parent.parent / "var" / "live" / self.uuid
        self.data_file = self.data_dir / "data.json"
        
        # Create directory structure
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize data structure
        self.data = self._get_empty_data_structure()
        
    def _get_empty_data_structure(self) -> Dict[str, Any]:
        """Get the base data structure matching existing live runner format"""
        return {
            "metadata": {
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "last_updated": int(time.time()),
                "uuid": self.uuid,
                "created_at": int(time.time())
            },
            "candles": [],
            "ema": [],
            "zones": {
                "supportSegments": [],
                "resistanceSegments": []
            },
            "chart_data": {
                "ema": {
                    "data_type": "ema",
                    "metadata": {"period": 20},
                    "points": []
                },
                "support": {
                    "data_type": "support",
                    "metadata": {},
                    "points": []
                },
                "resistance": {
                    "data_type": "resistance",
                    "metadata": {},
                    "points": []
                },
                "markers": {
                    "data_type": "marker",
                    "metadata": {},
                    "points": []
                },
                "zones": {
                    "support": [],
                    "resistance": []
                },
                "indicators": {
                    "ema": []
                }
            },
            "chartData": {},  # Will be populated as copy of chart_data
            "markers": [],
            "orderBoxes": [],
            # Flexible extensions - can add any new data types here
            "extensions": {
                "breakouts": [],
                "events": [],
                "alerts": [],
                "patterns": [],
                "volume_analysis": {},
                "custom_indicators": {}
            }
        }
    
    def add_candles(self, candles: List[Dict[str, Any]]) -> None:
        """Add candle data with automatic rolling window"""
        # Keep last 1000 candles
        self.data["candles"] = candles[-1000:] if len(candles) > 1000 else candles
        self._update_timestamp()
    
    def add_ema_points(self, ema_points: List[Dict[str, Any]], period: int = 20) -> None:
        """Add EMA points with period metadata"""
        self.data["ema"] = ema_points[-500:] if len(ema_points) > 500 else ema_points
        self.data["chart_data"]["ema"]["metadata"]["period"] = period
        self.data["chart_data"]["ema"]["points"] = self.data["ema"]
        self.data["chart_data"]["indicators"]["ema"] = self.data["ema"]
        self._update_timestamp()
    
    def add_support_zones(self, support_zones: List[Dict[str, Any]]) -> None:
        """Add support zone segments"""
        self.data["zones"]["supportSegments"] = support_zones[-50:] if len(support_zones) > 50 else support_zones
        self.data["chart_data"]["support"]["points"] = support_zones[-50:] if len(support_zones) > 50 else support_zones
        self.data["chart_data"]["zones"]["support"] = support_zones[-50:] if len(support_zones) > 50 else support_zones
        self._update_timestamp()
    
    def add_resistance_zones(self, resistance_zones: List[Dict[str, Any]]) -> None:
        """Add resistance zone segments"""
        self.data["zones"]["resistanceSegments"] = resistance_zones[-50:] if len(resistance_zones) > 50 else resistance_zones
        self.data["chart_data"]["resistance"]["points"] = resistance_zones[-50:] if len(resistance_zones) > 50 else resistance_zones
        self.data["chart_data"]["zones"]["resistance"] = resistance_zones[-50:] if len(resistance_zones) > 50 else resistance_zones
        self._update_timestamp()
    
    def add_marker(self, time: int, value: float, marker_type: str, metadata: Optional[Dict] = None) -> None:
        """Add a single marker point"""
        marker_point = {
            "time": time,
            "value": value,
            "marker_type": marker_type,
            **(metadata or {})
        }
        self.data["chart_data"]["markers"]["points"].append(marker_point)
        # Keep last 100 markers
        if len(self.data["chart_data"]["markers"]["points"]) > 100:
            self.data["chart_data"]["markers"]["points"] = self.data["chart_data"]["markers"]["points"][-100:]
        self._update_timestamp()
    
    def add_breakout(self, breakout_data: Dict[str, Any]) -> None:
        """Add breakout detection to extensions"""
        self.data["extensions"]["breakouts"].append(breakout_data)
        # Keep last 50 breakouts
        if len(self.data["extensions"]["breakouts"]) > 50:
            self.data["extensions"]["breakouts"] = self.data["extensions"]["breakouts"][-50:]
        self._update_timestamp()
    
    def add_event(self, event_data: Dict[str, Any]) -> None:
        """Add any event to extensions"""
        self.data["extensions"]["events"].append(event_data)
        # Keep last 200 events
        if len(self.data["extensions"]["events"]) > 200:
            self.data["extensions"]["events"] = self.data["extensions"]["events"][-200:]
        self._update_timestamp()
    
    def add_custom_indicator(self, name: str, points: List[Dict[str, Any]], metadata: Optional[Dict] = None) -> None:
        """Add custom indicator to extensions"""
        self.data["extensions"]["custom_indicators"][name] = {
            "points": points[-500:] if len(points) > 500 else points,
            "metadata": metadata or {},
            "data_type": "custom_indicator"
        }
        self._update_timestamp()
    
    def add_extension_data(self, extension_type: str, data: Any) -> None:
        """Add any extension data - completely flexible"""
        self.data["extensions"][extension_type] = data
        self._update_timestamp()
    
    def update_from_live_runner_output(self, live_output: Dict[str, Any]) -> None:
        """Update data from existing live runner output format"""
        # Copy existing structure
        if "candles" in live_output:
            self.add_candles(live_output["candles"])
        
        if "ema" in live_output:
            self.add_ema_points(live_output["ema"])
        
        if "zones" in live_output:
            if "supportSegments" in live_output["zones"]:
                self.add_support_zones(live_output["zones"]["supportSegments"])
            if "resistanceSegments" in live_output["zones"]:
                self.add_resistance_zones(live_output["zones"]["resistanceSegments"])
        
        if "chart_data" in live_output:
            self.data["chart_data"].update(live_output["chart_data"])
        
        # Ensure chartData is synchronized with chart_data
        self.data["chartData"] = self.data["chart_data"].copy()
        
        self._update_timestamp()
    
    def _update_timestamp(self) -> None:
        """Update last_updated timestamp"""
        self.data["metadata"]["last_updated"] = int(time.time())
    
    def save(self) -> None:
        """Save data to JSON file"""
        # Ensure chartData is synchronized
        self.data["chartData"] = self.data["chart_data"].copy()
        
        # Atomic write - write to temp file first, then rename
        temp_file = self.data_file.with_suffix('.tmp')
        try:
            with open(temp_file, 'w') as f:
                json.dump(self.data, f, indent=2, default=str)
            temp_file.rename(self.data_file)
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            raise e
    
    def load(self) -> Dict[str, Any]:
        """Load data from JSON file"""
        if self.data_file.exists():
            with open(self.data_file, 'r') as f:
                self.data = json.load(f)
            return self.data
        return self.data
    
    def get_file_path(self) -> str:
        """Get the file path for API access"""
        return str(self.data_file)
    
    def cleanup_old_data(self, max_age_hours: int = 24) -> None:
        """Clean up old data based on age"""
        current_time = int(time.time())
        max_age_seconds = max_age_hours * 3600
        
        # Clean old candles
        self.data["candles"] = [
            candle for candle in self.data["candles"]
            if current_time - candle.get("time", 0) < max_age_seconds
        ]
        
        # Clean old events
        self.data["extensions"]["events"] = [
            event for event in self.data["extensions"]["events"]
            if current_time - event.get("time", 0) < max_age_seconds
        ]
        
        # Clean old breakouts
        self.data["extensions"]["breakouts"] = [
            breakout for breakout in self.data["extensions"]["breakouts"]
            if current_time - breakout.get("break_time", 0) < max_age_seconds
        ]
        
        self._update_timestamp()
        self.save()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current data"""
        return {
            "uuid": self.uuid,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "last_updated": self.data["metadata"]["last_updated"],
            "candles_count": len(self.data["candles"]),
            "support_zones_count": len(self.data["zones"]["supportSegments"]),
            "resistance_zones_count": len(self.data["zones"]["resistanceSegments"]),
            "ema_points_count": len(self.data["ema"]),
            "markers_count": len(self.data["chart_data"]["markers"]["points"]),
            "breakouts_count": len(self.data["extensions"]["breakouts"]),
            "events_count": len(self.data["extensions"]["events"]),
            "custom_indicators": list(self.data["extensions"]["custom_indicators"].keys()),
            "file_path": str(self.data_file)
        }
