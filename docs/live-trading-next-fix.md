# Live Trading `next()` Method Fix - Documentation

## Problem Statement

When running live trading with multiple data feeds (EURUSD, GBPAUD, USDCHF), the strategy's `next()` method was only being called once instead of for each new bar. Additionally, there were issues with:
- Missing bars: Some feeds didn't have bars when processing started
- Duplicate `next()` calls: The same bar was being processed multiple times

## Root Cause Analysis

1. **Backtrader Synchronization**: Backtrader synchronizes multiple data feeds and only calls `next()` when all feeds have data for the same timestamp. If any feed returns `False` (no data), backtrader may exit without calling `next()`.

2. **Stale Data Logic**: Previous implementation tried to reuse old bars when new bars weren't available, which caused synchronization issues.

3. **Bar Timing**: Bars from different symbols arrive at slightly different times, causing feeds to have bars for different timestamps in their queues.

4. **Duplicate Processing**: Backtrader's internal synchronization mechanism could call `next()` multiple times for the same bar during a single `run()` call.

## Solution Overview

### 1. Fixed Data Feed Synchronization

**File**: `trading-bot/src/data/mt5_data_feed.py`

**Changes**:
- **Removed stale data logic**: Feeds now only return `True` if they have a new bar in the queue
- **Removed `fed_bar_this_run` flag**: This was preventing proper synchronization
- **Simplified `_load()` method**: 
  - Returns `True` only when a new bar is available
  - Returns `False` when no new bars are available
  - No longer reuses previous bars

**Key Code Changes**:
```python
# Before: Complex logic with stale data reuse
if len(self.live_bar_queue) > 0:
    # Feed bar
    return True
elif self.last_fed_bar is not None and not self.fed_stale_this_run:
    # Reuse stale data - REMOVED
    return True

# After: Simple logic - only feed new bars
if len(self.live_bar_queue) > 0:
    # Feed next live bar
    self.live_mode = True
    bar = self.live_bar_queue.popleft()
    # ... populate lines ...
    return True
else:
    # No new bars - return False
    return False
```

### 2. Added Wait Mechanism for Bar Synchronization

**File**: `trading-bot/main.py`

**Changes**:
- **Added wait logic**: Checks if all feeds have bars before processing
- **Timestamp matching**: Ensures all feeds have bars for the same timestamp (at the front of their queues)
- **Detailed logging**: Logs which feeds are missing bars or have mismatched timestamps
- **Skip processing**: Only processes when all conditions are met

**Key Code Changes**:
```python
if has_new_bars:
    # Check if all feeds have bars for the same timestamp
    all_have_bars = all(len(feed.live_bar_queue) > 0 for feed in live_feeds)
    
    if all_have_bars:
        # Check if front bars have same timestamp
        bar_times = []
        bar_info = {}
        for feed in live_feeds:
            if len(feed.live_bar_queue) > 0:
                bar = feed.live_bar_queue[0]
                bar_times.append(bar['datetime'])
                bar_info[feed.symbol] = bar['datetime']
        
        # Only proceed if all timestamps match
        if len(set(bar_times)) == 1:
            logger.info(f"All feeds have bars for timestamp {bar_times[0]}, proceeding...")
            # Process bars...
        else:
            logger.warning(f"Bars are for different timestamps: {bar_info}. Waiting...")
            continue
    else:
        missing_feeds = [feed.symbol for feed in live_feeds if len(feed.live_bar_queue) == 0]
        logger.warning(f"Not all feeds have bars yet. Missing: {missing_feeds}. Waiting...")
        continue
```

### 3. Fixed Duplicate `next()` Calls

**File**: `trading-bot/src/strategies/BreakRetestStrategy.py`

**Changes**:
- **Added timestamp tracking**: Tracks the last processed timestamp (not bar number, since bar numbers reset on each `run()`)
- **Duplicate detection**: Prevents processing the same timestamp twice
- **Logging**: Logs when duplicate calls are detected and skipped

**Key Code Changes**:
```python
def __init__(self):
    # ... existing code ...
    # Track last processed timestamp to prevent duplicate processing
    self.last_processed_timestamp = None

def next(self):
    # Get current bar info
    current_bar_time = self.data.datetime.datetime(0)
    current_bar_num = len(self.data)
    
    # Check if we've already processed this timestamp
    if self.last_processed_timestamp == current_bar_time:
        print(f"SKIPPING DUPLICATE next() call - Bar #{current_bar_num} at {current_bar_time}")
        return
    
    # Mark this timestamp as processed
    self.last_processed_timestamp = current_bar_time
    
    # Process the bar
    super().next()
```

## Files Modified

1. **`trading-bot/src/data/mt5_data_feed.py`**
   - Removed stale data reuse logic
   - Simplified `_load()` method
   - Removed `fed_stale_this_run` flag
   - Removed `fed_bar_this_run` flag

2. **`trading-bot/main.py`**
   - Added wait mechanism to check all feeds have matching timestamps
   - Added detailed logging for debugging
   - Only processes when all conditions are met

3. **`trading-bot/src/strategies/BreakRetestStrategy.py`**
   - Added duplicate detection using timestamp
   - Prevents processing same bar twice

## How It Works Now

### Bar Processing Flow

1. **Bar Detection**: Monitoring threads detect new bars and add them to queues
2. **Wait for Synchronization**: Main loop waits until all feeds have bars for the same timestamp
3. **Validation**: Checks that:
   - All feeds have at least one bar in queue
   - All front bars have the same timestamp
4. **Processing**: Only when all conditions are met:
   - Calls `prepare_for_next_run()` on all feeds
   - Calls `cerebro.run()` to process bars
   - Strategy's `next()` is called once per bar
5. **Duplicate Prevention**: If `next()` is called again for the same timestamp, it's skipped

### Example Flow

```
1. EURUSD detects bar at 01:32:00 → Queue: [01:32:00]
2. GBPAUD detects bar at 01:32:00 → Queue: [01:32:00]
3. USDCHF detects bar at 01:32:00 → Queue: [01:32:00]
4. Main loop checks: All feeds have bars ✓, All timestamps match ✓
5. Process bars → next() called once for 01:32:00
6. If next() called again for 01:32:00 → Skipped (duplicate)
```

## Testing Results

### Before Fix
- `next()` called only once when going live
- Missing bars caused processing to fail
- Duplicate `next()` calls processed same bar multiple times

### After Fix
- ✅ `next()` called once per new bar when all feeds have bars for the same timestamp
- ✅ No missing bars: Processing only happens when all feeds are ready
- ✅ No duplicate processing: Each timestamp is processed only once
- ✅ Better logging: Clear messages when waiting or skipping

## Log Messages

### Success
```
INFO | All feeds have bars for timestamp 2025-12-11 01:32:00, proceeding...
INFO | *** PROCESSING NEW BARS (iteration 345). Queue sizes: {'EURUSD': 1, 'GBPAUD': 1, 'USDCHF': 1} ***
```

### Waiting for Bars
```
WARNING | *** SKIPPING: Not all feeds have bars yet. Queue sizes: {'EURUSD': 1, 'GBPAUD': 1, 'USDCHF': 0}. Missing: ['USDCHF']. Waiting... ***
```

### Timestamp Mismatch
```
WARNING | *** SKIPPING: Bars are for different timestamps. Queue sizes: {...}, Timestamps: {'EURUSD': 01:32:00, 'GBPAUD': 01:33:00, 'USDCHF': 01:32:00}. Waiting... ***
```

### Duplicate Detection
```
SKIPPING DUPLICATE next() call - Bar #1 at 2025-12-11 01:32:00
```

## Key Principles

1. **No Stale Data**: Never reuse old bars - only process when new bars are available
2. **Synchronization**: Always wait for all feeds to have bars for the same timestamp
3. **Idempotency**: Prevent duplicate processing of the same bar
4. **Transparency**: Clear logging of what's happening and why

## Future Improvements

Potential enhancements:
1. **Timeout handling**: If a feed consistently doesn't receive bars, log an alert
2. **Bar ordering**: Process bars in chronological order if timestamps don't match
3. **Queue management**: Limit queue size to prevent memory issues
4. **Performance monitoring**: Track how long it takes for all feeds to synchronize

## Related Files

- `trading-bot/src/data/mt5_data_feed.py` - Data feed implementation
- `trading-bot/main.py` - Main live trading loop
- `trading-bot/src/strategies/BreakRetestStrategy.py` - Strategy implementation
- `trading-bot/src/strategies/BaseStrategy.py` - Base strategy class

## Date

Documentation created: December 11, 2025

