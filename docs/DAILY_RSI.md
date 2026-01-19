# Daily RSI Implementation

## Overview

Daily RSI is a technical indicator that calculates the Relative Strength Index (RSI) using daily aggregated price data, regardless of the trading timeframe. This provides a higher-level view of market momentum that complements the regular timeframe RSI.

### Key Features

- **Timeframe Independent**: Works with any trading timeframe (M30, H1, H4, etc.)
- **Daily Aggregation**: Automatically aggregates lower timeframe data into daily bars using `replaydata()`
- **Constant Throughout Day**: Daily RSI stays constant throughout each trading day
- **Day-Based Updates**: Only updates when a new day starts
- **Visual Comparison**: Displayed alongside regular RSI on charts for easy comparison
- **Validated**: Mathematically verified against pandas-ta reference implementation

## How It Works

### 1. Data Source

Daily RSI uses the `daily_data` feed created by `cerebro.replaydata()` in `main.py`. This feed replays the main timeframe data at daily intervals. The `daily_data` array contains all intraday bars, so we filter it to get only one bar per day (the last bar of each day).

### 2. Daily Bar Aggregation

The system filters the `daily_data` feed to extract completed daily bars:

- Groups all bars by date (normalized to midnight)
- Takes the **last close** of each day as the daily close price
- This ensures we only use completed daily bars, not developing ones

**Note**: `replaydata()` doesn't automatically aggregate - it replays data at daily intervals but still contains all intraday bars. We filter to get true daily bars.

### 3. RSI Calculation

Daily RSI is calculated using the standard RSI formula (period=14) on the filtered daily closes:

```
RSI = 100 - (100 / (1 + RS))
where RS = Average Gain / Average Loss
```

The calculation uses **Wilder's smoothing method** for the moving averages:
- First average = Simple Moving Average of first `period` values
- Subsequent averages = `(Previous_Avg * (period - 1) + Current_Value) / period`

This matches the standard RSI calculation used by most libraries (verified against pandas-ta).

### 4. Alignment with Main Timeframe

Since Daily RSI has fewer data points (one per day), it's aligned with the main timeframe by:

1. Normalizing all dates to midnight for proper day matching
2. Merging Daily RSI values with main timeframe dates
3. Forward-filling Daily RSI values throughout each day
4. Ensuring all candles on the same day share the same Daily RSI value

## Implementation Details

### Files Modified

1. **`src/strategies/BaseStrategy.py`**
   - Stores reference to `daily_data` feed (created via `replaydata()`)
   - Sets `self.daily_data` for access in strategies and plotting

2. **`src/utils/plot.py`**
   - `extract_daily_rsi()`: Extracts Daily RSI from `strategy.daily_data` feed
   - `calculate_rsi_manual()`: Calculates RSI using Wilder's smoothing method
   - `add_rsi()`: Displays both regular RSI and Daily RSI on charts
   - `plotly_plot()`: Integrates Daily RSI extraction and display

3. **`main.py`**
   - Creates daily data feeds using `cerebro.replaydata()` for each symbol
   - Maps daily data feeds for strategy access via `cerebro.daily_data_mapping`

### Key Functions

#### `extract_daily_rsi(strategy, data_len, df_dates)`

Extracts Daily RSI from the `strategy.daily_data` feed (created by `replaydata()`).

**Process:**
1. Gets `daily_data` from `strategy.daily_data`
2. Extracts all bars from `daily_data` (contains all intraday bars)
3. Filters to get only one bar per day (last bar of each day)
4. Groups by date (normalized to midnight) and takes last close
5. Calculates RSI from filtered daily closes using `calculate_rsi_manual()`
6. Aligns Daily RSI with main timeframe dates using merge-based forward-fill

**Returns:** `(has_daily_rsi: bool, daily_rsi: np.ndarray)`

**Note**: This uses the actual `daily_data` feed so any issues with `replaydata()` will be visible.

#### `calculate_rsi_manual(prices, period=14)`

Calculates RSI using Wilder's smoothing method (matches standard RSI implementations).

**Process:**
1. Calculates price changes (deltas)
2. Separates gains and losses
3. Applies Wilder's smoothing:
   - First average = SMA of first `period` values
   - Subsequent = `(Prev_Avg * (period - 1) + Current) / period`
4. Calculates RS = Average Gain / Average Loss
5. Calculates RSI = 100 - (100 / (1 + RS))

**Returns:** `np.ndarray` of RSI values (first `period` values are NaN)

**Validation**: Matches pandas-ta RSI calculation exactly (max diff: 0.000000)

## Usage

### In Your Strategy

Daily RSI data is available in your strategy through the `daily_data` reference:

```python
class MyStrategy(BaseStrategy):
    def next(self):
        # Access daily data feed
        if self.daily_data is not None:
            daily_close = self.daily_data.close[0]
            # Note: Daily RSI is calculated in plot.py, not as a strategy indicator
            # If you need Daily RSI in your strategy, calculate it manually
            # or use the extract_daily_rsi function from plot.py
        pass
```

**Note**: Daily RSI is currently calculated during plotting, not as a strategy indicator. If you need Daily RSI values in your strategy logic, you can:
1. Calculate it manually using `calculate_rsi_manual()` from `plot.py`
2. Or add it as a strategy indicator in `BaseStrategy.__init__()`

### On Charts

Daily RSI is automatically displayed when plotting:

```python
from main import backtesting
from src.utils.plot import plotly_plot
from src.models.timeframe import Timeframe
from datetime import datetime

results = backtesting(
    symbols=['EURGBP'],
    timeframe=Timeframe.H1,
    start_date=datetime(2025, 12, 1),
    end_date=datetime.now()
)

cerebro = results['cerebro']
data = results['data']['EURGBP']

plotly_plot(cerebro, data, 'EURGBP', symbol_index=0, height=1100)
```

**Chart Display:**
- **Regular RSI**: Solid blue line (#2962FF)
- **Daily RSI**: Dashed orange line (#FF9800)
- Both appear in the RSI subplot with separate legend entries

### Requirements

- **Minimum Data**: At least 15 days of data required for RSI(14) calculation
- **Timeframe**: Works with any timeframe (M1, M5, M15, M30, H1, H4, D1)

## Validation

A comprehensive validation script is provided to verify Daily RSI correctness.

### Running Validation

```python
# In a notebook or script:
from validate_daily_rsi import validate_daily_rsi_calculation
from src.models.timeframe import Timeframe
from datetime import datetime

validate_daily_rsi_calculation(
    symbols=['EURGBP'],
    timeframe=Timeframe.H1,
    start_date=datetime(2025, 12, 1),
    end_date=datetime.now()
)
```

### Validation Checks

The script validates multiple aspects:

1. **Consistency**
   - Extracts Daily RSI twice and compares results
   - Verifies extractions are identical (within floating-point tolerance)
   - Ensures reproducible results

2. **Constancy**
   - Verifies Daily RSI stays constant throughout each day
   - Checks that all candles on the same day have the same Daily RSI value
   - Reports any intraday changes (should be zero)

3. **Update Behavior**
   - Verifies Daily RSI only updates on day transitions
   - Ensures no updates occur within the same day
   - Reports any unexpected intraday updates (should be zero)

4. **Mathematical Correctness**
   - Compares RSI calculation against pandas-ta reference implementation
   - Verifies values match exactly (max diff: 0.000000)
   - Confirms Wilder's smoothing method is implemented correctly

5. **Edge Cases**
   - Validates RSI values are in valid range (0-100)
   - Checks proper NaN handling (first 14 days are NaN)
   - Verifies no sudden jumps (unrealistic changes)
   - Ensures length matches main data

### Expected Output

```
✅ ALL VALIDATIONS PASSED
   - Daily RSI extractions are consistent
   - Daily RSI stays constant throughout each day
   - Daily RSI only updates on day transitions

Additional Edge Case Validations...
✓ All Daily RSI values are in valid range (0-100)
✓ Daily RSI has proper NaN handling
✓ No sudden jumps in Daily RSI
✓ Daily RSI length matches main data length

Validating RSI calculation correctness...
✓ RSI calculation matches pandas-ta reference (max diff: 0.000000)
```

## Technical Notes

### Using `daily_data` from `replaydata()`

The implementation uses `strategy.daily_data` (created by `replaydata()`) to ensure:

1. **Visibility**: Any issues with `replaydata()` will be visible in the plot
2. **Consistency**: Uses the same data source the strategy would use
3. **Accuracy**: Filters to get only completed daily bars (last close of each day)
4. **Reliability**: Full control over filtering and aggregation logic

**Important**: `replaydata()` doesn't automatically aggregate - it replays data at daily intervals but still contains all intraday bars. We filter the `daily_data` array to get only one bar per day (the last bar of each day).

### Date Normalization

All dates are normalized to midnight (00:00:00) for proper day matching:

```python
date_normalized = pd.to_datetime(datetime).dt.normalize()
```

This ensures:
- All bars on the same calendar day are grouped together
- Proper alignment between daily RSI and main timeframe
- Consistent forward-filling throughout each day

### Forward-Filling Strategy

Daily RSI values are forward-filled using a merge-based approach:

1. Create mapping of normalized dates to Daily RSI values
2. Merge with main timeframe dates
3. Forward-fill any missing dates (handles weekends/holidays)
4. Ensures all candles on the same day share the same value

## Troubleshooting

### Daily RSI Not Appearing

**Issue**: Daily RSI doesn't show on chart

**Solutions**:
- Ensure you have at least 15 days of data
- Check that the strategy has access to daily data feed
- Verify extraction function is being called in `plotly_plot()`

### Daily RSI Changes During Day

**Issue**: Daily RSI values change within the same day

**Solutions**:
- This should not happen - indicates a bug
- Run validation script to identify the issue
- Check date normalization and alignment logic

### Daily RSI Matches Regular RSI

**Issue**: Daily RSI and Regular RSI are identical

**Solutions**:
- If trading on D1 timeframe, this is expected (both are daily)
- For lower timeframes, check aggregation logic
- Verify daily data feed is properly created

## Examples

### Example 1: H1 Trading with Daily RSI

```python
from main import backtesting
from src.models.timeframe import Timeframe
from datetime import datetime

results = backtesting(
    symbols=['EURGBP'],
    timeframe=Timeframe.H1,  # Trading on H1
    start_date=datetime(2025, 12, 1),
    end_date=datetime.now()
)
# Daily RSI will aggregate 24 H1 bars per day
```

### Example 2: M30 Trading with Daily RSI

```python
results = backtesting(
    symbols=['XAGUSD'],
    timeframe=Timeframe.M30,  # Trading on M30
    start_date=datetime(2025, 12, 1),
    end_date=datetime.now()
)
# Daily RSI will aggregate ~48 M30 bars per day
```

### Example 3: Multiple Symbols

```python
results = backtesting(
    symbols=['XAGUSD', 'XAUUSD', 'SOLUSD', 'EURGBP'],
    timeframe=Timeframe.H1,
    start_date=datetime(2025, 12, 1),
    end_date=datetime.now()
)
# Each symbol gets its own Daily RSI calculation
```

## Future Enhancements

Potential improvements for Daily RSI:

1. **Configurable Period**: Allow custom RSI period (currently fixed at 14)
2. **Weekly/Monthly RSI**: Extend to weekly and monthly aggregations
3. **Strategy Integration**: Direct access to Daily RSI in strategy logic
4. **Performance Optimization**: Cache daily aggregations for faster plotting

## References

- [RSI Indicator](https://www.investopedia.com/terms/r/rsi.asp)
- [Backtrader Documentation](https://www.backtrader.com/)
- [Pandas Time Series](https://pandas.pydata.org/docs/user_guide/timeseries.html)
