# Live Trading Restructure – Documentation

## Overview

The live trading functionality was completely broken. The process died immediately after starting, stdout/stderr logs were empty, chart overlays (EMA, zones) were missing, and the WebSocket connection was hardcoded to a specific IP. This document covers every change made to fix and restructure the system.

---

## Root Causes Identified

### 1. Process Dying Immediately (`live_store.py`)
The `start_live_runner_process` function used a `with open(...)` context manager for stdout/stderr file handles. The `with` block closed the file descriptors as soon as `Popen()` returned, which killed the subprocess's output pipes immediately.

### 2. No `snapshot.json` Written (`run_live.py`)
The old `run_live.py` in `fastapi-app/` was a minimal stub that fetched raw candles from MT5 but never:
- Computed EMA from close prices
- Extracted support/resistance zones via backtrader's BreakoutIndicator
- Built the `chartOverlayData` in the timestamp-keyed format the frontend expects
- Applied `env_overrides` from `params.json` before importing strategy code

### 3. WebSocket Hardcoded IP (`websocketService.ts`)
The client-side WebSocket URL was hardcoded to `ws://192.168.2.4:8000`, making it non-portable.

### 4. WebSocket Was Passive (`handlers.py`)
The WebSocket handler only waited for client messages – it never pushed file changes to the client. The frontend had to rely entirely on HTTP polling.

### 5. Double WebSocket Accept (`connection_manager.py`)
Both the handler and the connection manager called `websocket.accept()`, causing errors.

### 6. Schema Validation (`schemas.py`)
`LiveSessionStatus.state` didn't include `"unknown"`, and fields lacked defaults, causing validation errors.

---

## Files Changed

### Backend (FastAPI) – `fastapi-app/`

#### `app/services/live_store.py`
- **Fixed file handle bug**: Removed `with` context manager for stdout/stderr files. Files are now opened without `with` so they stay open for the subprocess lifetime.
- **Added `start_new_session=True`**: Detaches subprocess from parent process group so it survives if FastAPI restarts.
- **Fixed PYTHONPATH separator**: Changed hardcoded `;` to `os.pathsep` for cross-platform compatibility (`;` on Windows, `:` on Linux).

#### `run_live.py` (Complete Rewrite – v2)
The live runner was completely rewritten to mirror `web-app/backtests/runner/run_backtest.py`:

- **`env_overrides` applied first**: All environment variables from `params.json` → `env_overrides` are set via `os.environ` before any strategy imports. `importlib.reload(config_module)` ensures Config picks up the new values.
- **Real strategy execution**: Each tick, the runner feeds MT5 candles into backtrader and runs the **actual `BreakRetestStrategy`** (not a dummy). This causes `BaseStrategy.sync_indicator_data_to_chart()` to call `ChartOverlayManager.add_overlay_data()` for EMA, support, resistance, and markers – producing `chart_overlays.json`.
- **`set_chart_overlay_manager_for_job(session_dir)`**: Points the global `ChartOverlayManager` singleton at the live session directory, so `chart_overlays.json` is written there.
- **Overlay data read from `chart_overlays.json`**: No manual EMA/zone computation. Everything comes from the strategy via `ChartOverlayManager`, identical to backtesting.
- **`chartOverlayData` format**: Reads the raw overlay format `{timestamp: {data_feed_index: {ema, support, resistance}}}` and transforms to the frontend format:
  ```json
  {
    "data": {
      "SOLUSD": {
        "1708700400": {"ema": 123.45, "support": 120.0, "resistance": 130.0},
        "1708704000": {"ema": 124.0, "resistance": 130.0}
      }
    },
    "trades": {}
  }
  ```
- **`snapshot.json` in ResultJson format**: Each symbol entry includes `candles`, `chartOverlayData`, `chartData`, `ema`, `zones`, `markers`, `orderBoxes`.
- **Graceful MT5 retry**: If MT5 is unavailable, the runner keeps running and retries every 30s instead of dying.
- **SIGTERM handling**: Graceful shutdown on SIGTERM.
- **stdout/stderr flushing**: `sys.stdout.flush()` / `sys.stderr.flush()` after every tick so logs appear in the UI immediately.
- **Atomic JSON writes**: Uses `.tmp` → `os.replace()` with retry for Windows PermissionError.

#### `app/websocket/handlers.py` (Complete Rewrite)
- **Active file pushing**: The WebSocket handler now polls session files every 2 seconds and pushes changes to the client:
  - `status_update` – full status.json + stdout/stderr/params
  - `snapshot_update` – full snapshot.json (ResultJson)
  - `logs_update` – stdout/stderr only (when they change independently)
- **mtime tracking**: Only sends data when files actually change (compares `os.stat().st_mtime`).
- **Client message handling**: Supports `ping` → `pong`, `request_snapshot`, `request_status`.
- **Uses `asyncio.wait_for`** with timeout for non-blocking receive + push loop.

#### `app/websocket/connection_manager.py`
- **Removed double `websocket.accept()`**: The handler accepts the connection; the manager just registers it.
- **Removed duplicate `connection_established` message**.

#### `app/models/schemas.py`
- Added `"unknown"` to `LiveSessionStatus.state` Literal.
- Added `= None` / `= False` defaults to all Optional fields and `has_snapshot`.

### Frontend (React) – `react-app/`

#### `src/services/websocketService.ts` (Complete Rewrite)
- **Dynamic URL**: Uses `VITE_API_TARGET` env var (falls back to `location.host`), replacing hardcoded IP.
- **New message types**: `StatusUpdateMessage`, `SnapshotUpdateMessage`, `LogsUpdateMessage`.
- **Proper reconnect**: Exponential backoff (2s × attempt, max 10 attempts).
- **Ping interval cleanup**: `clearInterval` on disconnect (was leaking intervals).
- **Legacy compat**: `ChartUpdateMessage` is aliased to `SnapshotUpdateMessage`.

#### `src/store/slices/liveSlice.ts` (Rewrite)
- **WebSocket-driven reducers**: `wsStatusUpdate`, `wsSnapshotUpdate`, `wsLogsUpdate` directly update Redux state from WS messages.
- **HTTP polling fallback**: Only polls when WebSocket is not connected (2s interval).
- **Proper cleanup**: `disconnectWebSocket` thunk called on unmount.
- **Removed `updateSnapshotWithWebSocketData`** (old chart_update handler).

#### `src/pages/LivePage.tsx` (Rewrite)
Restructured to closely mimic `BacktestPage.tsx`:
- **Same card layout**: Stats → Status/Charts → stdout/stderr → Parameters.
- **Status dot**: Shows running/stopped/error state with colored dot (matches backtest).
- **WS indicator pill**: Shows "WS" (green) or "Poll" (orange) in header.
- **Cleanup on unmount**: Disconnects WebSocket and resets Redux state.
- **Simplified data flow**: No retry logic or previous-state tracking – WS pushes handle it.
- **Copy buttons**: SVG copy icons for stdout/stderr (matches backtest style).

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  run_live.py (subprocess)                                   │
│                                                             │
│  Every 60s:                                                 │
│    1. Fetch candles from MT5                                │
│    2. Run real BreakRetestStrategy via backtrader cerebro    │
│       → BaseStrategy.sync_indicator_data_to_chart()          │
│       → ChartOverlayManager writes chart_overlays.json       │
│         (EMA, support, resistance, markers, trades)           │
│    3. Read chart_overlays.json, transform to frontend format │
│    4. Write snapshot.json + status.json                     │
│    5. Print tick + strategy logs to stdout (captured by Popen)│
│    6. Flush stdout/stderr                                   │
└─────────────────┬───────────────────────────────────────────┘
                  │ files on disk
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  WebSocket handler (handlers.py)                            │
│                                                             │
│  Every 2s:                                                  │
│    - Check mtime of status.json, snapshot.json, logs        │
│    - If changed → push to connected WS clients              │
│      • status_update (status + stdout + stderr + params)    │
│      • snapshot_update (full ResultJson)                    │
│      • logs_update (stdout + stderr only)                   │
└─────────────────┬───────────────────────────────────────────┘
                  │ WebSocket messages
                  ▼
┌─────────────────────────────────────────────────────────────┐
│  React Frontend                                             │
│                                                             │
│  liveSlice.ts receives WS messages:                         │
│    • wsStatusUpdate → updates status + logs in Redux        │
│    • wsSnapshotUpdate → updates snapshot (ResultJson)       │
│    • wsLogsUpdate → updates stdout/stderr in status         │
│                                                             │
│  LivePage.tsx renders:                                      │
│    • Stats card (from snapshot.stats)                       │
│    • Charts (ChartsContainer → ChartPanel → ChartComponent) │
│    • stdout/stderr cards                                    │
│    • Parameters card                                        │
│                                                             │
│  Fallback: HTTP polling every 2s when WS disconnected       │
└─────────────────────────────────────────────────────────────┘
```

---

## Chart Overlay Data Format

The frontend `ChartComponent.tsx` reads overlays from `sym.chartOverlayData.data[symbol]`, which is a timestamp-keyed object:

```typescript
// ChartComponent.tsx reads:
const symbolData = cd.data[symbol]  // e.g. cd.data["SOLUSD"]

// EMA: entries with .ema field
emaData = Object.entries(symbolData)
  .filter(([_, data]) => data.ema !== undefined)
  .map(([timestamp, data]) => ({ time: parseInt(timestamp), value: data.ema }))

// Zones: ChartZoneManager reads .support and .resistance fields
// and creates segments from value changes and nulls
```

The runner reads `chart_overlays.json` (written by `ChartOverlayManager` during strategy execution) and transforms it in `build_symbol_entry()`:
```python
# chart_overlays.json raw format (written by ChartOverlayManager):
# { "overlays": { "1708700400": { "0": { "ema": 123.45, "support": 120.0 } } } }
#
# Transformed to frontend format in build_symbol_entry():
# { "data": { "SOLUSD": { "1708700400": { "ema": 123.45, "support": 120.0 } } } }
```

---

## Regarding stdout/stderr (Issue #2)

All output is captured by the `Popen(stdout=stdout_file)` mechanism in `live_store.py`.

Since v2, the runner executes the **real `BreakRetestStrategy`** via `cerebro.run()` on each tick. This means:
- Backtrader strategy logs (indicator calculations, trade decisions) now appear in stdout
- The strategy's `print()` and `logger` calls are captured
- Each tick shows: runner tick line + strategy execution output

Note: This is **not** live order execution – the strategy runs on historical candles to generate chart overlays. Actual live order placement would require `MT5Broker` integration (separate feature).

---

## Session 2 Fixes – Chart Overlay Alignment & Multi-Symbol Stability

### 7. Daily RSI Data Feeds (`run_live.py`)
The `BreakRetestStrategy` requires daily-timeframe RSI, which `main.backtesting()` provides via `cerebro.replaydata()`. The live runner was missing this, causing `TypeError: '>' not supported between instances of 'NoneType' and 'int'` when `daily_rsi` was `None`.

**Initial attempt**: Used `cerebro.replaydata()` — but this **shifts data feed indices** inside backtrader, causing cross-symbol price contamination (e.g. GBPCAD trade recording XAU price `5168.02999` as `entry_executed_price`).

**Final fix**: Manually resample H1 candles to daily using `pandas.resample("1D")` and add as separate `PandasData` feeds with `_DAILY` suffix. `BaseStrategy.__init__` finds them by name. This keeps data feed indices clean.

**Insufficient data guard**: RSI(14) needs ≥15 daily bars, but 200 H1 candles only yields ~8–12 days. If any symbol has too few daily bars, daily feeds are skipped entirely and `Config.check_for_daily_rsi` is set to `False`, so the strategy skips the RSI confirmation gracefully.

### 8. Timestamp Alignment – 2-Hour Offset (`BaseStrategy.py`, `BreakRetestStrategy.py`)
Chart overlays (EMA, zones, markers, order boxes) appeared **2 H1 candles early**.

**Root cause**: Backtrader strips timezone info from datetimes internally. `data.datetime.datetime(0)` returns a **naive** datetime. Calling `.timestamp()` on a naive datetime in Python assumes **local time** (UTC+2 on the server), producing a Unix timestamp 7200 seconds too small.

**Fix**: Added `BaseStrategy._utc_timestamp(dt)` static method that forces `tzinfo=timezone.utc` on naive datetimes before calling `.timestamp()`. Applied to all timestamp conversions:
- `sync_indicator_data_to_chart()` — EMA/support/resistance overlay timestamps
- `BreakRetestStrategy.next()` — `current_time` for markers and overlay data
- Trade placement (`placed_on`), execution (`executed_on`), cancellation, and closing (`closed_on`) timestamps

### 9. Frontend Crash – Time Ordering (`ChartComponent.tsx`)
`lightweight-charts` threw `Assertion failed: data must be asc ordered by time` when order box `openTime > closeTime` (caused by the cross-symbol contamination in fix #7).

**Fix**: Added a guard at line 565 to swap `openTime`/`closeTime` if out of order before passing to `setData()`.

### 10. Trades Leaking Across Symbols (`run_live.py`)
The top-level `trades` field in each symbol's snapshot entry dumped **all** trades from every symbol. Fixed `build_symbol_entry()` to filter trades by the current symbol only.

### 11. Undefined `showRetestOrders` (`ChartComponent.tsx`)
`showRetestOrders` was referenced but never declared, causing a lint error. Defaulted to `true` (show all retest order markers).

### 12. `max_candles` NoneType (`run_live.py`)
`params.json` can have `max_candles: null`. Changed `int(backtest_args.get("max_candles", 200))` to `int(backtest_args.get("max_candles") or 200)` to handle both missing and `None` cases.

---

## Files Changed (Session 2)

| File | Changes |
|------|---------|
| `fastapi-app/run_live.py` | Replaced `replaydata()` with manual daily resample; added insufficient-data guard; fixed trades leak; fixed `max_candles` NoneType |
| `src/strategies/BaseStrategy.py` | Added `_utc_timestamp()` static method; updated `sync_indicator_data_to_chart` to use it; added `timezone` import |
| `src/strategies/BreakRetestStrategy.py` | Replaced all `.timestamp()` calls with `self._utc_timestamp()` (placement, execution, cancellation, closing) |
| `react-app/src/components/ChartComponent.tsx` | Added time-ordering guard for order boxes; fixed undefined `showRetestOrders` |

---

## Testing

1. **Restart FastAPI server** to pick up all backend changes.
2. **Start a new live session** from the React UI.
3. **Verify**:
   - `chart_overlays.json` is generated in the session directory
   - stdout shows backtrader strategy logs (not just tick lines)
   - Chart shows EMA line and support/resistance zones (from chart_overlays.json)
   - Markers and order boxes align correctly with their candles (no 2-candle offset)
   - Order boxes have correct prices per symbol (no cross-symbol contamination)
   - WebSocket indicator shows "WS" (green) in header
   - Stopping the session works (status changes to "stopped")
   - Works with 4–5 symbols without crashing
