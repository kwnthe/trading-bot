import json
import math
import os
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from ..models.chart_markers import ChartDataType, ChartMarkerType

class ChartOverlayManager:
    """
    Manages dynamic writing of chart overlay data to JSON file during strategy execution.
    Keeps minimal data by storing only essential parameters for each timestamp.
    """
    
    def __init__(self, json_file_path: str = "chart_overlays.json"):
        self.json_file_path = json_file_path
        self.overlays: Dict[int, Dict[int, Dict[str, Any]]] = {}
        self.trades: List[Dict[str, Any]] = []
        self._load_existing_data()
    
    @classmethod
    def for_job_directory(cls, job_dir: Path) -> 'ChartOverlayManager':
        """Create ChartOverlayManager for a specific job directory"""
        json_path = job_dir / "chart_overlays.json"
        return cls(str(json_path))
    
    def _load_existing_data(self):
        """Load existing chart overlays from JSON file if it exists"""
        if os.path.exists(self.json_file_path):
            try:
                with open(self.json_file_path, 'r') as f:
                    loaded_data = json.load(f)
                    # Handle new format with overlays and trades
                    if 'overlays' in loaded_data:
                        self.overlays = {int(k): {int(data_feed_index): v for data_feed_index, v in data.items()} for k, data in loaded_data['overlays'].items()}
                        self.trades = loaded_data.get('trades', [])
                    else:
                        # Handle old format (backward compatibility)
                        self.overlays = {int(k): {int(data_feed_index): v for data_feed_index, v in data.items()} for k, data in loaded_data.items()}
                        self.trades = []
            except (json.JSONDecodeError, IOError):
                self.overlays = {}
                self.trades = []
        else:
            self.overlays = {}
            self.trades = []
    
    def add_overlay_data(self, datetime_number: int, data_type: ChartDataType, data_feed_index: int = 0, **kwargs):
        """
        Add overlay data for a specific datetime and data type
        
        Args:
            datetime_number: Unix timestamp
            data_type: Type of chart data
            data_feed_index: Index of the data feed (0 for first symbol, 1 for second, etc.)
            **kwargs: Additional data based on type
        """
        # Initialize the datetime entry if it doesn't exist
        if datetime_number not in self.overlays:
            self.overlays[datetime_number] = {}
        
        # Initialize the data feed entry if it doesn't exist
        if data_feed_index not in self.overlays[datetime_number]:
            self.overlays[datetime_number][data_feed_index] = {}
        
        # Create parameter key based on data type only (not data feed index)
        param_key = f"{data_type.value}"
        
        # Store minimal data based on type
        if data_type == ChartDataType.MARKER:
            # For markers, use the marker type as the key (not "marker")
            marker_type = kwargs.get('marker_type', 'diamond').value if hasattr(kwargs.get('marker_type', 'diamond'), 'value') else str(kwargs.get('marker_type', 'diamond'))
            direction = kwargs.get('direction')
            # Convert direction to string if it's an enum
            if hasattr(direction, '__str__'):
                direction = str(direction)  # This will give "uptrend", "downtrend", etc.
            elif direction is not None:
                direction = str(direction)
            
            marker_data = {
                'price': kwargs.get('price'),
                'time': datetime_number,  # Use actual timestamp instead of candle_index
                'direction': direction  # Add direction metadata as string
            }
            # Remove None values to keep data minimal
            marker_data = {k: v for k, v in marker_data.items() if v is not None}
            # Use marker_type as the key instead of param_key
            self.overlays[datetime_number][data_feed_index][marker_type] = marker_data
            
        elif data_type in [ChartDataType.SUPPORT, ChartDataType.RESISTANCE, ChartDataType.EMA]:
            # For support/resistance/EMA, store only the value (time is already the key)
            points = kwargs.get('points', [])
            if points:
                # Take the first point's value since time is redundant
                first_point = points[0]
                if isinstance(first_point, dict) and 'value' in first_point:
                    value = first_point['value']
                    # Validate the value: must be finite and not zero for support/resistance
                    try:
                        numeric_value = float(value)
                        is_valid = (
                            not math.isnan(numeric_value) and 
                            not math.isinf(numeric_value) and
                            numeric_value != 0 or 
                            data_type == ChartDataType.EMA  # EMA can be 0 in some cases
                        )
                        if is_valid:
                            self.overlays[datetime_number][data_feed_index][param_key] = numeric_value
                        else:
                            print(f"Warning: Skipping invalid {data_type.value} value: {value} at time {datetime_number}")
                    except (ValueError, TypeError):
                        print(f"Warning: Skipping non-numeric {data_type.value} value: {value} at time {datetime_number}")
    
    def add_trade(self, placed_on: int, executed_on: int = None, closed_on: int = None, closed_on_price: float = None, state: str = None, **kwargs):
        """
        Add or update trade data in the trades collection.
        Can be called multiple times to update the same trade through its lifecycle.
        
        Args:
            placed_on: Unix timestamp when trade was placed (required, used as unique identifier)
            executed_on: Unix timestamp when trade was executed (optional)
            closed_on: Unix timestamp when trade was closed (optional)
            closed_on_price: Price at which trade was closed (optional)
            state: Trade state as string (optional)
            **kwargs: Additional trade data
        """
        # Look for existing trade with this placed_on timestamp
        existing_trade = None
        for i, trade in enumerate(self.trades):
            if trade.get('placed_on') == placed_on:
                existing_trade = i
                break
        
        trade_data = {
            'placed_on': placed_on,
            **kwargs
        }
        
        # Add optional fields if provided
        if executed_on is not None:
            trade_data['executed_on'] = executed_on
        if closed_on is not None:
            trade_data['closed_on'] = closed_on
        if closed_on_price is not None:
            trade_data['closed_on_price'] = closed_on_price
        if state is not None:
            trade_data['state'] = state
        
        if existing_trade is not None:
            # Update existing trade
            self.trades[existing_trade].update(trade_data)
        else:
            # Add new trade
            self.trades.append(trade_data)
    
    def save_to_file(self):
        """Save current overlays and trades to JSON file"""
        try:
            # Sort overlays by datetime for consistent output
            sorted_overlays = dict(sorted(self.overlays.items()))
            
            data = {
                'overlays': sorted_overlays,
                'trades': self.trades
            }
            
            with open(self.json_file_path, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save chart overlays to {self.json_file_path}: {e}")
    
    def clear_data(self):
        """Clear all overlay and trade data"""
        self.overlays.clear()
        self.trades.clear()
        if os.path.exists(self.json_file_path):
            try:
                os.remove(self.json_file_path)
            except IOError:
                pass
    
    def get_overlays_for_time_range(self, start_time: int, end_time: int) -> Dict[int, Dict[str, Any]]:
        """Get overlay data for a specific time range"""
        return {
            dt: data for dt, data in self.overlays.items()
            if start_time <= dt <= end_time
        }
    
    def get_raw_data(self) -> Dict[str, Any]:
        """
        Return the raw overlay and trades data as-is without any conversion
        Returns:
            Dict with structure: {overlays: {timestamp: {data_feed_index: {data_type: value}}}, trades: [...]}
        """
        return {
            'overlays': self.overlays,
            'trades': self.trades
        }
    
# Global instance for use across the application
_chart_overlay_manager = None

def get_chart_overlay_manager(job_dir: Path = None) -> ChartOverlayManager:
    """Get the global chart overlay manager instance"""
    global _chart_overlay_manager
    if _chart_overlay_manager is None:
        if job_dir is not None:
            _chart_overlay_manager = ChartOverlayManager.for_job_directory(job_dir)
        else:
            _chart_overlay_manager = ChartOverlayManager()
    return _chart_overlay_manager

def reset_chart_overlay_manager():
    """Reset the global chart overlay manager (useful for new backtests)"""
    global _chart_overlay_manager
    if _chart_overlay_manager is not None:
        _chart_overlay_manager.clear_data()
    _chart_overlay_manager = None

def set_chart_overlay_manager_for_job(job_dir: Path):
    """Set the chart overlay manager to use a specific job directory"""
    global _chart_overlay_manager
    _chart_overlay_manager = ChartOverlayManager.for_job_directory(job_dir)
