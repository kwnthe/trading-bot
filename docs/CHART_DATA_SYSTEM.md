# Chart Data System

This document describes the new flexible chart data system that provides consistent data visualization between live trading and backtesting.

## Overview

The new `set_chart_data` system replaces the simple `set_chart_marker` method with a more flexible approach that can handle different types of data:

- **Markers**: Point markers (diamonds, circles, etc.) for events like order placements
- **Support**: Support level lines/segments
- **Resistance**: Resistance level lines/segments  
- **EMA**: EMA line data

Note: Zones are collections of support and resistance levels, not a separate data type.

## Key Components

### ChartDataType Enum
```python
class ChartDataType(Enum):
    MARKER = 'marker'          # Point markers
    SUPPORT = 'support'        # Support levels
    RESISTANCE = 'resistance'  # Resistance levels
    EMA = 'ema'               # EMA lines
```

### ChartData and ChartDataPoint Classes
- `ChartDataPoint`: Individual data point with time, value, and extra metadata
- `ChartData`: Container for multiple points of the same type with metadata

## Usage Examples

### 1. Setting Markers (Events)
```python
# Old way (still works for backward compatibility)
self.set_chart_marker(self.candle_index, current_price, marker_type=ChartMarkerType.RETEST_ORDER_PLACED)

# New way - more flexible
self.set_chart_data(ChartDataType.MARKER, 
                   candle_index=self.candle_index, 
                   price=current_price, 
                   marker_type=ChartMarkerType.RETEST_ORDER_PLACED)
```

### 2. Setting Support/Resistance Levels
```python
# Set support levels
support_points = [
    {'time': 1234567890, 'value': 1.2500},
    {'time': 1234567950, 'value': 1.2510}
]
self.set_support_data(support_points, data_feed_index=0)

# Set resistance levels  
resistance_points = [
    {'time': 1234567890, 'value': 1.2600},
    {'time': 1234567950, 'value': 1.2610}
]
self.set_resistance_data(resistance_points, data_feed_index=0)
```

### 3. Setting EMA Data
```python
ema_points = [
    {'time': t, 'value': v} for t, v in zip(timestamps, ema_values)
]
self.set_ema_data(ema_points, data_feed_index=0, period=20)
```

### 4. Automatic Sync from Indicators
```python
# Automatically sync current indicator values to chart
self.sync_indicator_data_to_chart(data_feed_index=0)
```

## Live Trading Integration

The live trading system (`run_live.py`) has been updated to output data in the new format:

```python
chart_data = {
    'ema': {
        'data_type': 'ema',
        'metadata': {'period': ema_len},
        'points': ema_points
    },
    'support': {
        'data_type': 'support', 
        'metadata': {},
        'points': support_points
    },
    'resistance': {
        'data_type': 'resistance',
        'metadata': {},
        'points': resistance_points
    },
    'markers': {
        'data_type': 'marker',
        'metadata': {},
        'points': marker_points
    }
}
```

## Backward Compatibility

- Old `set_chart_marker` method still works
- Live trading output maintains old format alongside new `chart_data` field
- Existing chart rendering code continues to work

## Extensibility

The system is designed to be easily extended:

1. **Add new data types**: Extend `ChartDataType` enum
2. **Add new marker types**: Extend `ChartMarkerType` enum  
3. **Add custom metadata**: Use `**kwargs` in convenience methods
4. **Add new convenience methods**: Follow the pattern of `set_support_data`, etc.

## Implementation in BreakRetestStrategy

The strategy now uses the new system:

```python
# For order placement markers
self.set_chart_data(ChartDataType.MARKER, 
                   data_feed_index=i,
                   candle_index=self.candle_index, 
                   price=current_price, 
                   marker_type=ChartMarkerType.RETEST_ORDER_PLACED)

# For automatic indicator sync (live trading only)
if not self._is_backtesting():
    self.sync_indicator_data_to_chart(i)
```

## Benefits

1. **Consistency**: Same data format between live and backtesting
2. **Flexibility**: Easy to add new data types and metadata
3. **Extensibility**: Simple to extend for future requirements
4. **Backward Compatibility**: Existing code continues to work
5. **Rich Metadata**: Support for additional information like periods, colors, etc.

## Future Enhancements

Potential future additions:
- Custom colors and styling per data type
- Multiple EMA periods
- Zone confidence levels
- Volume profile data
- Custom drawing tools
- Real-time data streaming optimizations
