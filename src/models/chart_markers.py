from enum import Enum
from typing import Any, Dict, List, Optional

class ChartDataType(Enum):
    """Types of chart data that can be stored"""
    MARKER = 'marker'  # Point markers (diamonds, circles, etc.)
    SUPPORT = 'support'  # Support level lines/segments
    RESISTANCE = 'resistance'  # Resistance level lines/segments
    EMA = 'ema'  # EMA line data

class ChartMarkerType(Enum):
    RETEST_ORDER_PLACED = 'retest_order_placed'

MARKER_TYPE_TO_MARKER_SYMBOL = {
    ChartMarkerType.RETEST_ORDER_PLACED: 'diamond',
}

class ChartDataPoint:
    """Individual chart data point"""
    def __init__(self, 
                 time: Optional[int] = None, 
                 value: Optional[float] = None, 
                 **kwargs):
        self.time = time
        self.value = value
        self.extra_data = kwargs

class ChartData:
    """Container for chart data of a specific type"""
    def __init__(self, data_type: ChartDataType, **kwargs):
        self.data_type = data_type
        self.points: List[ChartDataPoint] = []
        self.metadata = kwargs
    
    def add_point(self, point: ChartDataPoint):
        """Add a data point"""
        self.points.append(point)
    
    def add_point_at_time(self, time: int, value: float, **kwargs):
        """Convenience method to add a point with time and value"""
        point = ChartDataPoint(time=time, value=value, **kwargs)
        self.add_point(point)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'data_type': self.data_type.value,
            'metadata': self.metadata,
            'points': [
                {
                    'time': p.time,
                    'value': p.value,
                    **p.extra_data
                } for p in self.points
            ]
        }