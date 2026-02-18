# Dynamic Chart Overlay System

This system allows strategies to dynamically write chart overlay data to a JSON file during execution instead of calculating everything at the end.

## How it works

1. **ChartOverlayManager**: Handles dynamic JSON writing with minimal data storage
2. **BaseStrategy.set_chart_data()**: Now automatically writes to chart_overlays.json
3. **run_backtest.py**: Reads from chart_overlays.json instead of generating overlay data

## JSON Format

```json
{
  "1640995200": {
    "marker": {
      "type": "retest_order_placed",
      "price": 1.25,
      "time": 1640995200
    },
    "ema": 1.251,
    "support": 1.245,
    "resistance": 1.260
  }
}
```

**Key changes:**
- **Parameter names**: Now use `ema`, `support`, `resistance`, `marker` (no `_0` suffix)
- **Simplified values**: EMA/support/resistance store just the numeric value (not objects with `time`/`value`)
- **Timestamp**: Markers now include `time` field with actual Unix timestamp (not `candle_index`)
- **Time**: The datetime is the key, so no redundant `time` field needed for EMA/support/resistance

## Usage in Strategies

The existing `set_chart_data()` calls in your strategies will now automatically write to the JSON file:

```python
# This call now writes to chart_overlays.json dynamically
self.set_chart_data(ChartDataType.MARKER, 
                  data_feed_index=i,
                  candle_index=self.candle_index, 
                  price=current_price, 
                  marker_type=ChartMarkerType.RETEST_ORDER_PLACED)
```

## Data Types

- **marker**: Point markers (diamonds, circles, etc.)
- **support**: Support level lines/segments  
- **resistance**: Resistance level lines/segments
- **ema**: EMA line data

## Key Features

- **Minimal data**: Only stores essential parameters
- **Dynamic**: Writes data in real-time during strategy execution
- **Backward compatible**: Still works with existing chart system
- **Live trading ready**: Can be used for live trading visualization

## File Location

The overlay data is saved to `chart_overlays.json` in the project root directory.
