"""
Chart data exporter for trading bot.
Provides clean JSON export of chart data including zones, EMA, and markers.
"""

import json
import math
from typing import Dict, List, Any, Optional
from datetime import datetime


class ChartDataExporter:
    """Exports chart data in clean JSON format for frontend consumption."""
    
    @staticmethod
    def export_chart_data(
        symbol: str,
        times: List[int],
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
        support_values: List[float],
        resistance_values: List[float],
        ema_values: Optional[List[float]] = None,
        markers: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Export chart data in clean format.
        
        Args:
            symbol: Trading symbol
            times: List of timestamps
            opens: List of open prices
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
            support_values: List of support values (NaN where no support)
            resistance_values: List of resistance values (NaN where no resistance)
            ema_values: Optional list of EMA values
            markers: Optional list of marker data
            
        Returns:
            Dictionary containing chart data
        """
        
        # Convert candlestick data
        candlesticks = []
        for i in range(len(times)):
            candlesticks.append({
                'time': times[i],
                'open': opens[i],
                'high': highs[i],
                'low': lows[i],
                'close': closes[i]
            })
        
        # Convert zones to horizontal line segments
        support_zones = ChartDataExporter._convert_to_zones(times, support_values, 'support')
        resistance_zones = ChartDataExporter._convert_to_zones(times, resistance_values, 'resistance')
        
        # Convert EMA to line data
        ema_line = []
        if ema_values:
            for i in range(len(times)):
                if not math.isnan(ema_values[i]):
                    ema_line.append({
                        'time': times[i],
                        'value': ema_values[i]
                    })
        
        # Process markers
        processed_markers = []
        if markers:
            for marker in markers:
                processed_markers.append({
                    'time': marker.get('time'),
                    'value': marker.get('value'),
                    'type': marker.get('type', 'diamond'),
                    'color': marker.get('color', '#FF0000'),
                    'size': marker.get('size', 8)
                })
        
        return {
            'symbol': symbol,
            'timestamp': datetime.utcnow().isoformat(),
            'candlesticks': candlesticks,
            'zones': {
                'support': support_zones,
                'resistance': resistance_zones
            },
            'indicators': {
                'ema': ema_line
            },
            'markers': processed_markers
        }
    
    @staticmethod
    def _convert_to_zones(times: List[int], values: List[float], zone_type: str) -> List[Dict[str, Any]]:
        """
        Convert array of values to zone segments.
        
        Args:
            times: List of timestamps
            values: List of values (NaN where no zone)
            zone_type: Type of zone ('support' or 'resistance')
            
        Returns:
            List of zone segments
        """
        zones = []
        start_idx = None
        
        def is_nan(x: float) -> bool:
            return x is None or (isinstance(x, float) and math.isnan(x))
        
        for i, value in enumerate(values):
            if not is_nan(value) and start_idx is None:
                # Start of a new zone
                start_idx = i
                continue
            
            if start_idx is not None:
                is_last = i == len(values) - 1
                value_changed = (not is_nan(value)) and (value != values[start_idx])
                
                if is_nan(value) or value_changed or is_last:
                    # End of current zone
                    end_idx = i if (is_last and not is_nan(value) and not value_changed) else i - 1
                    if end_idx >= start_idx:
                        zones.append({
                            'type': zone_type,
                            'startTime': times[start_idx],
                            'endTime': times[end_idx],
                            'value': float(values[start_idx]),
                            'color': '#2962FF' if zone_type == 'support' else '#E91E63'
                        })
                    start_idx = i if (not is_nan(value) and value_changed) else None
        
        return zones
    
    @staticmethod
    def save_to_file(data: Dict[str, Any], filepath: str) -> None:
        """Save chart data to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @staticmethod
    def to_json(data: Dict[str, Any]) -> str:
        """Convert chart data to JSON string."""
        return json.dumps(data, indent=2)
