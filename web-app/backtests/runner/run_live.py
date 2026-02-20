from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# WebSocket client for streaming chart updates
try:
    import asyncio
    import websockets
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError
    WEBSOCKET_AVAILABLE = True
    print("WebSocket streaming enabled")
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("Warning: websockets library not available, WebSocket streaming disabled")

# Check for MetaTrader5 availability
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("Warning: MetaTrader5 not available, live trading disabled")

# Import WebSocket broadcast function
try:
    from web_app.backtests.consumers import broadcast_chart_update
    WEBSOCKET_BROADCAST_AVAILABLE = True
    print("WebSocket broadcast enabled")
except ImportError:
    # Fallback for different import paths
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from backtests.consumers import broadcast_chart_update
        WEBSOCKET_BROADCAST_AVAILABLE = True
        print("WebSocket broadcast enabled (fallback path)")
    except ImportError:
        WEBSOCKET_BROADCAST_AVAILABLE = False
        print("Warning: WebSocket broadcast not available, live streaming disabled")

# Import LiveDataManager at module level
try:
    from web_app.backtests.runner.live_data_manager import LiveDataManager
except ImportError:
    # Fallback for different import paths
    try:
        from live_data_manager import LiveDataManager
    except ImportError:
        LiveDataManager = None
        print("Warning: LiveDataManager not available, live data features disabled")

# Import ForexLeverage at module level
try:
    from src.brokers.ForexLeverage import ForexLeverage
except ImportError:
    # Fallback for different import paths
    try:
        from brokers.ForexLeverage import ForexLeverage
    except ImportError:
        ForexLeverage = None
        print("Warning: ForexLeverage not available, using default broker")


def _write_json(path: Path, payload: Any) -> None:
  # On Windows, os.replace() can temporarily fail with PermissionError if another
  # process is reading the destination file. Retry briefly instead of crashing.
  tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
  tmp.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')

  last_err: Exception | None = None
  for attempt in range(6):
    try:
      os.replace(tmp, path)
      last_err = None
      break
    except PermissionError as e:
      last_err = e
      time.sleep(0.03 * (attempt + 1))

  if last_err is not None:
    # Best-effort cleanup; keep the previous JSON in place if the destination
    # is locked.
    try:
      if tmp.exists():
        tmp.unlink()
    except Exception:
      pass
    return


def _load_json(path: Path) -> dict[str, Any]:
  return json.loads(path.read_text(encoding='utf-8'))


def _repo_root() -> Path:
  # .../web-app/backtests/runner/run_live.py -> runner -> backtests -> web-app -> repo root
  return Path(__file__).resolve().parents[3]


def _to_unix_seconds(dt: datetime) -> int:
  return int(dt.timestamp())


def _segments_from_constant_levels(times_s: list[int], values: list[float]) -> list[dict[str, Any]]:
  segs: list[dict[str, Any]] = []
  start_idx: int | None = None

  def is_nan(x: float) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))

  for i, v in enumerate(values):
    if not is_nan(v) and start_idx is None:
      start_idx = i
      continue

    if start_idx is not None:
      is_last = i == len(values) - 1
      price_changed = (not is_nan(v)) and (v != values[start_idx])

      if is_nan(v) or price_changed or is_last:
        end_idx = i if (is_last and not is_nan(v) and not price_changed) else i - 1
        if end_idx >= start_idx:
          segs.append({
            'startTime': times_s[start_idx],
            'endTime': times_s[end_idx],
            'value': float(values[start_idx]),
          })
        start_idx = i if (not is_nan(v) and price_changed) else None

  return segs


def _compute_ema(times_s: list[int], closes: list[float], ema_len: int) -> list[dict[str, Any]]:
  """Compute EMA values for the given price data."""
  if not times_s or not closes:
    return []

  try:
    import pandas as pd
    ema_vals = pd.Series(closes, dtype='float64').ewm(span=int(ema_len), adjust=False).mean().to_list()
    out: list[dict[str, Any]] = []
    for i, val in enumerate(ema_vals):
      if val is None or (isinstance(val, float) and math.isnan(val)):
        continue
      out.append({'time': times_s[i], 'value': float(val)})
    return out
  except Exception:
    return []


def _get_zones_from_strategy(times_s: list[int], highs: list[float], lows: list[float], closes: list[float], symbol: str, lookback: int) -> dict[str, Any]:
  """
  Get zones from the actual BreakoutIndicator by replicating the backtest setup exactly.
  This uses the same BreakRetestStrategy that the backtest uses.
  """
  print(f"!!! CACHE CLEARED VERSION 5.0 - {symbol} - {datetime.now().isoformat()} !!!")
  print(f"DEBUG: Starting _get_zones_from_strategy for {symbol}")
  
  if not times_s or not highs or not lows or not closes:
    print(f"DEBUG: Early return - missing data for {symbol}")
    return {'resistanceSegments': [], 'supportSegments': []}
  
  print(f"DEBUG: About to enter try block for {symbol}")
  
  try:
    print(f"DEBUG: Inside try block for {symbol}")
    # Add project root to path
    project_root = str(Path(__file__).parent.parent.parent.parent)
    sys.path.insert(0, project_root)
    sys.path.insert(0, str(Path(project_root) / "src"))  # Add src to path for indicators import
    
    import backtrader as bt
    import pandas as pd
    import os
    
    # Set environment variables BEFORE any imports (critical for BreakoutIndicator)
    env_vars = {
      'price_precision': '5',
      'volume_precision': '1',  # Fixed: must be >= 1 for config validation
      'mode': 'backtest',
      'market_type': 'forex',
      'breakout_lookback_period': '50',
      'zone_inversion_margin_atr': '0.5',
      'breakout_min_strength_atr': '0.5',
      'atr_length': '14',
      'ema_length': '20',
      'volume_ma_length': '20',
      'rr': '2.0',
      'initial_equity': '10000.0'
    }
    
    for k, v in env_vars.items():
      os.environ[k] = v
      print(f"DEBUG: Set env var {k}={v}")
    
    # Set up environment like the backtest does
    from src.utils.config import Config, load_config
    
    # Load config to ensure BreakoutIndicator has all required parameters
    try:
      config = load_config()
      print(f"DEBUG: Config loaded successfully for {symbol}")
      print(f"DEBUG: Config breakout_lookback_period: {getattr(config, 'breakout_lookback_period', 'NOT_SET')}")
      print(f"DEBUG: Config atr_length: {getattr(config, 'atr_length', 'NOT_SET')}")
    except Exception as e:
      print(f"DEBUG: Config loading failed for {symbol}: {e}")
      # Set minimal config for testing
      config = load_config()
    
    from src.strategies.BreakRetestStrategy import BreakRetestStrategy
    from src.brokers.backtesting_broker import BacktestingBroker
    from indicators.BreakoutIndicator import BreakoutIndicator  # Match main.py pattern
    from indicators.BreakRetestIndicator import BreakRetestIndicator  # Match main.py pattern

    print(f"DEBUG: Imports successful for {symbol}")

    df = pd.DataFrame({
      'datetime': pd.to_datetime(times_s, unit='s', utc=True),
      'high': highs,
      'low': lows,
      'close': closes,
      'open': closes,  # Use close as open since we don't have open prices
      'volume': [1] * len(times_s),  # Dummy volume
    })
    
    print(f"DEBUG: DataFrame created for {symbol} with {len(df)} rows")
    
    # Create cerebro setup exactly like the backtest
    cerebro = bt.Cerebro(stdstats=False)
    
    # Set up data_indicators like the backtest
    cerebro.data_indicators = {}
    cerebro.data_state = {}
    cerebro.candle_data = {}
    cerebro.chart_markers = {}
    
    # Add commission info if ForexLeverage is available
    if ForexLeverage is not None:
        cerebro.broker.addcommissioninfo(ForexLeverage())
        print(f"DEBUG: Added ForexLeverage commission info for {symbol}")
    else:
        print(f"DEBUG: ForexLeverage not available, using default broker commission for {symbol}")
    
    # Use PandasData with proper datetime column
    data = bt.feeds.PandasData(dataname=df, datetime='datetime')
    data._name = symbol
    cerebro.adddata(data, name=symbol)
    
    # CRITICAL: Populate data_indicators with actual indicator instances BEFORE adding strategy
    # This replicates exactly what BaseStrategy.__init__ does
    original_data_index = 0  # We only have one data feed
    
    # Get the actual data feed from cerebro (this is the key fix)
    actual_data_feed = cerebro.datas[0]  # This is the properly initialized data feed
    
    cerebro.data_indicators[original_data_index] = {
        'breakout': BreakoutIndicator(actual_data_feed, symbol=symbol),
        'break_retest': BreakRetestIndicator(actual_data_feed, symbol=symbol),
        'atr': bt.indicators.ATR(actual_data_feed, period=Config.atr_length),
        'ema': bt.indicators.EMA(actual_data_feed.close, period=Config.ema_length),
        'volume_ma': bt.indicators.SMA(actual_data_feed.volume, period=Config.volume_ma_length),
        'rsi': bt.indicators.RSI(actual_data_feed.close, period=14),
        'symbol': symbol,
        'data': actual_data_feed
    }
    
    cerebro.data_state[original_data_index] = {
        'just_broke_out': None,
        'breakout_trend': None,
        'support': None,
        'resistance': None,
    }
    cerebro.candle_data[original_data_index] = []
    cerebro.chart_markers[original_data_index] = {}
    
    print(f"DEBUG: data_indicators populated for {symbol}: {list(cerebro.data_indicators[0].keys())}")
    
    # The key insight: we need to run the actual strategy to populate BreakoutIndicator arrays
    # Use much longer warm-up period and better error handling
    
    class ZoneExtractionStrategy(bt.Strategy):
        def __init__(self):
            super().__init__()
            self.bar_count = 0
            self.warmup_bars = 200  # Much longer warm-up period for BreakoutIndicator
            
        def next(self):
            self.bar_count += 1
            
            # Only try to access indicators after very long warm-up period
            if self.bar_count < self.warmup_bars:
                return
                
            # CRITICAL: Connect to cerebro's data_indicators that we already populated
            if not hasattr(self, 'data_indicators'):
                self.data_indicators = cerebro.data_indicators
                self.data_state = cerebro.data_state
                self.candle_data = cerebro.candle_data
                self.chart_markers = cerebro.chart_markers
            
            # Access the breakout indicator to ensure it's calculated
            try:
                if hasattr(self, 'data_indicators') and 0 in self.data_indicators:
                    breakout = self.data_indicators[0].get('breakout')
                    if breakout is not None:
                        # Check if we have enough data before accessing
                        if len(breakout.lines.resistance1.array) > 0 and len(breakout.lines.support1.array) > 0:
                            # Access the lines to ensure they're calculated
                            _ = breakout.lines.support1[0]
                            _ = breakout.lines.resistance1[0]
                            
                            # Debug: Check if arrays have values
                            import numpy as np
                            res_vals = np.asarray(breakout.lines.resistance1.array, dtype=float)
                            sup_vals = np.asarray(breakout.lines.support1.array, dtype=float)
                            
                            if self.bar_count == self.warmup_bars + 1:  # Only print once
                                print(f"DEBUG Strategy: {symbol} - After warm-up, resistance1 array length: {len(res_vals)}")
                                print(f"DEBUG Strategy: {symbol} - After warm-up, support1 array length: {len(sup_vals)}")
                                if len(res_vals) > 0 and len(sup_vals) > 0:
                                    print(f"DEBUG Strategy: {symbol} - SUCCESS: BreakoutIndicator has values!")
                        else:
                            if self.bar_count == self.warmup_bars + 1:  # Only print once
                                print(f"DEBUG Strategy: {symbol} - BreakoutIndicator arrays still empty after warm-up")
            except Exception as e:
                if self.bar_count == self.warmup_bars + 1:  # Only print once
                    print(f"DEBUG Strategy: {symbol} - Error accessing indicator: {e}")
    
    # Add the zone extraction strategy
    cerebro.addstrategy(ZoneExtractionStrategy)
    
    print(f"DEBUG: Running cerebro with zone extraction strategy for {symbol}")
    
    # Run cerebro to calculate the indicators properly
    results = cerebro.run()
    
    print(f"DEBUG: Cerebro run completed for {symbol}, results: {len(results)}")
    
    # Now extract the zones from the calculated indicator
    print(f"DEBUG: Extracting zones from calculated indicator for {symbol}")
    
    # Extract zones exactly like the backtest does
    zones = {"supportSegments": [], "resistanceSegments": []}
    
    # Extract zones from data_indicators where the real BreakoutIndicator is calculated
    if hasattr(cerebro, 'data_indicators'):
        print(f"DEBUG Strategy: {symbol} - Extracting from calculated data_indicators")
        try:
            indicators = cerebro.data_indicators.get(0)  # symbol_index 0
            print(f"DEBUG Strategy: {symbol} - indicators from data_indicators: {type(indicators)}")
            breakout = indicators.get("breakout") if indicators else None
            print(f"DEBUG Strategy: {symbol} - breakout from data_indicators: {type(breakout)}")
            
            if breakout is not None:
                import numpy as np
                res_vals = np.asarray(breakout.lines.resistance1.array, dtype=float)
                sup_vals = np.asarray(breakout.lines.support1.array, dtype=float)
                
                print(f"DEBUG Strategy: {symbol} - resistance1 array length: {len(res_vals)}")
                print(f"DEBUG Strategy: {symbol} - support1 array length: {len(sup_vals)}")
                print(f"DEBUG Strategy: {symbol} - Sample resistance values: {res_vals[:10]}")
                print(f"DEBUG Strategy: {symbol} - Sample support values: {sup_vals[:10]}")
                
                # Check if we have real values (not all NaN and not empty)
                if len(res_vals) > 0 and len(sup_vals) > 0 and not (np.all(np.isnan(res_vals)) and np.all(np.isnan(sup_vals))):
                    zones["resistanceSegments"] = _segments_from_constant_levels(times_s, res_vals.tolist())
                    zones["supportSegments"] = _segments_from_constant_levels(times_s, sup_vals.tolist())
                    
                    print(f"DEBUG Strategy: {symbol} - SUCCESS: Generated {len(zones['supportSegments'])} support, {len(zones['resistanceSegments'])} resistance zones from real BreakoutIndicator")
                    if zones['supportSegments']:
                        print(f"DEBUG Strategy: Sample support: {zones['supportSegments'][0]}")
                    if zones['resistanceSegments']:
                        print(f"DEBUG Strategy: Sample resistance: {zones['resistanceSegments'][0]}")
                    
                    return zones
                else:
                    print(f"DEBUG Strategy: {symbol} - ERROR: BreakoutIndicator arrays are empty or NaN, using fallback")
            else:
                print(f"DEBUG Strategy: {symbol} - ERROR: BreakoutIndicator is None, using fallback")
        except Exception as e:
            print(f"Warning: data_indicators extraction failed: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"DEBUG Strategy: {symbol} - No zones generated")
    return {'resistanceSegments': [], 'supportSegments': []}
    
  except Exception as e:
    # If strategy execution fails, use fallback
    print(f"Warning: BreakoutIndicator failed: {e}")
    import traceback
    traceback.print_exc()
    return {'resistanceSegments': [], 'supportSegments': []}


def _segments_from_constant_levels(times_s: list[int], values: list[float]) -> list[dict[str, Any]]:
  """
  Convert an array of (mostly-NaN) constant price levels into horizontal segments.
  Each segment is {startTime, endTime, value}.
  This is the same logic used in backtest.
  """
  segs: list[dict[str, Any]] = []
  start_idx: int | None = None

  def is_nan(x: float) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))

  for i, v in enumerate(values):
    if not is_nan(v) and start_idx is None:
      start_idx = i
      continue

    if start_idx is not None:
      is_last = i == len(values) - 1
      price_changed = (not is_nan(v)) and (v != values[start_idx])

      if is_nan(v) or price_changed or is_last:
        end_idx = i if (is_last and not is_nan(v) and not price_changed) else i - 1
        if end_idx >= start_idx:
          segs.append(
            {
              "startTime": times_s[start_idx],
              "endTime": times_s[end_idx],
              "value": float(values[start_idx]),
            }
          )
        start_idx = None

  return segs


def main() -> int:
  ap = argparse.ArgumentParser()
  ap.add_argument('--session-dir', required=True)
  ap.add_argument('--poll-seconds', type=float, default=1.0)
  ap.add_argument('--max-candles', type=int, default=500)
  args = ap.parse_args()

  session_dir = Path(args.session_dir).resolve()
  params_path = session_dir / 'params.json'
  status_path = session_dir / 'status.json'
  snapshot_path = session_dir / 'snapshot.json'

  params = _load_json(params_path)

  # Apply env overrides BEFORE importing repo code (Config loads at import time).
  for k, v in (params.get('env_overrides') or {}).items():
    os.environ[str(k)] = str(v)

  repo_root = _repo_root()
  os.chdir(repo_root)
  if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

  try:
    # MT5 is already imported at module level as mt5

    def _status_patch(patch: dict[str, Any]) -> None:
      try:
        prev = _load_json(status_path)
      except Exception:
        prev = {}
      payload = {**prev, **patch, 'updated_at': datetime.now(tz=timezone.utc).isoformat()}
      _write_json(status_path, payload)

    _status_patch({'state': 'running', 'error': None, 'python_executable': sys.executable})

    # ---- MT5 init/login ----
    if not MT5_AVAILABLE:
      print("ERROR: MetaTrader5 not available - cannot run live trading")
      _status_patch({'state': 'error', 'error': 'MetaTrader5 not available'})
      return 1
    
    mt5_path = os.environ.get('MT5_PATH') or None
    if mt5_path:
      initialized = mt5.initialize(path=mt5_path)
    else:
      initialized = mt5.initialize()
    if not initialized:
      raise RuntimeError(f'MT5 initialize failed: {mt5.last_error()}')

    login_raw = os.environ.get('MT5_LOGIN')
    password = os.environ.get('MT5_PASSWORD')
    server = os.environ.get('MT5_SERVER')
    if not login_raw or not password or not server:
      raise RuntimeError('Missing MT5 credentials (MT5_LOGIN/MT5_PASSWORD/MT5_SERVER)')

    try:
      login = int(login_raw)
    except Exception:
      raise RuntimeError('MT5_LOGIN must be an int')

    if not mt5.login(login, password=password, server=server):
      raise RuntimeError(f'MT5 login failed: {mt5.last_error()}')

    symbols_raw = os.environ.get('MT5_SYMBOL') or ''
    symbols = [s.strip().rstrip('.') for s in symbols_raw.split(',') if s.strip()]
    if not symbols:
      raise RuntimeError('Missing MT5_SYMBOL')
    print(f"DEBUG: Processed symbols: {symbols}")

    timeframe_str = (os.environ.get('MT5_TIMEFRAME') or 'H1').upper()
    tf_map = {
      'M1': mt5.TIMEFRAME_M1,
      'M5': mt5.TIMEFRAME_M5,
      'M15': mt5.TIMEFRAME_M15,
      'M30': mt5.TIMEFRAME_M30,
      'H1': mt5.TIMEFRAME_H1,
      'H4': mt5.TIMEFRAME_H4,
      'D1': mt5.TIMEFRAME_D1,
    }
    tf = tf_map.get(timeframe_str)
    if tf is None:
      raise RuntimeError(f'Invalid MT5_TIMEFRAME: {timeframe_str}')

    # Verify symbols visible
    verified: list[str] = []
    for sym in symbols:
      info = mt5.symbol_info(sym)
      if info is None:
        raise RuntimeError(f'Symbol not found: {sym}')
      if not info.visible:
        if not mt5.symbol_select(sym, True):
          raise RuntimeError(f'Failed to enable symbol: {sym}')
      verified.append(sym)
    symbols = verified

    latest_seq = 0

    try:
      from src.utils.config import Config

      default_lookback = int(getattr(Config, 'breakout_lookback_period', 50) or 50)
    except Exception:
      default_lookback = 50

    try:
      ema_len = int(os.environ.get('EMA_LENGTH') or 0)
    except Exception:
      ema_len = 0

    while True:
      # Basic stats from account
      acct = mt5.account_info()
      stats: dict[str, Any] = {}
      if acct:
        stats = {
          'balance': float(acct.balance),
          'equity': float(acct.equity),
          'profit': float(acct.profit),
          'margin': float(acct.margin),
          'margin_free': float(acct.margin_free),
        }

      out_symbols: dict[str, Any] = {}
      live_data_managers: dict[str, Any] = {}
      
      # Only use LiveDataManager if it's available
      if LiveDataManager is not None:
        for sym in symbols:
          # Initialize LiveDataManager for each symbol if available
          live_data_managers[sym] = LiveDataManager(sym, timeframe_str)
        
        rates = mt5.copy_rates_from_pos(sym, tf, 0, int(args.max_candles))
        candles = []
        times_s: list[int] = []
        highs: list[float] = []
        lows: list[float] = []
        closes: list[float] = []
        if rates is not None:
          for r in rates:
            ts = int(r['time'])
            o = float(r['open'])
            h = float(r['high'])
            l = float(r['low'])
            c = float(r['close'])
            candles.append({
              'time': ts,
              'open': o,
              'high': h,
              'low': l,
              'close': c,
            })
            times_s.append(ts)
            highs.append(h)
            lows.append(l)
            closes.append(c)

        ema = _compute_ema(times_s, closes, ema_len)
        
        # Get zones from strategy indicators for consistency
        zones = _get_zones_from_strategy(times_s, highs, lows, closes, sym, default_lookback)
        
        support_segments = zones.get('supportSegments', [])
        resistance_segments = zones.get('resistanceSegments', [])

        # Convert to new chart data format for consistency with backtesting.
        # Include nested structure (zones, indicators) so frontend chartData.zones.support / chartData.indicators.ema work.
        
        # Create timestamp-keyed data format for frontend
        timestamp_keyed_data = {}
        for i, ts in enumerate(times_s):
            if i < len(closes) and i < len(ema):
                timestamp_keyed_data[str(ts)] = {
                    'ema': ema[i]['value'] if i < len(ema) and ema[i] else None,
                    'support': None,  # Will be populated from zones
                    'resistance': None,  # Will be populated from zones
                }
        
        # Add support/resistance values from zones
        for seg in support_segments:
            start_time = seg.get('startTime')
            end_time = seg.get('endTime')
            value = seg.get('value')
            if start_time and end_time and value:
                # Find all timestamps in this segment and set support value
                for ts in times_s:
                    if start_time <= ts <= end_time and str(ts) in timestamp_keyed_data:
                        timestamp_keyed_data[str(ts)]['support'] = value
        
        for seg in resistance_segments:
            start_time = seg.get('startTime')
            end_time = seg.get('endTime')
            value = seg.get('value')
            if start_time and end_time and value:
                # Find all timestamps in this segment and set resistance value
                for ts in times_s:
                    if start_time <= ts <= end_time and str(ts) in timestamp_keyed_data:
                        timestamp_keyed_data[str(ts)]['resistance'] = value
        
        chart_data = {
            'ema': {
                'data_type': 'ema',
                'metadata': {'period': ema_len},
                'points': ema
            },
            'support': {
                'data_type': 'support',
                'metadata': {},
                'points': support_segments
            },
            'resistance': {
                'data_type': 'resistance',
                'metadata': {},
                'points': resistance_segments
            },
            'markers': {
                'data_type': 'marker',
                'metadata': {},
                'points': []  # Will be populated by live trading events
            },
            # Frontend expects chartData.zones.support / chartData.zones.resistance (array of { startTime, endTime, value })
            'zones': {
                'support': support_segments,
                'resistance': resistance_segments,
            },
            # Frontend expects chartData.indicators.ema (array of { time, value })
            'indicators': {
                'ema': ema,
            },
        }

        out_symbols[sym] = {
          'candles': candles,
          'ema': ema,  # Keep for backward compatibility
          'zones': zones,  # Keep for backward compatibility
          'chart_data': chart_data,  # snake_case (API returns as-is)
          'chartData': chart_data,   # camelCase for frontend sym.chartData
          'timestamp_keyed_data': timestamp_keyed_data,  # For WebSocket broadcasting
          'markers': [],  # Keep for backward compatibility
          'orderBoxes': [],
        }
        
        # Update LiveDataManager with all the processed data (if available)
        if LiveDataManager is not None and sym in live_data_managers:
          live_data_manager = live_data_managers[sym]
          live_data_manager.update_from_live_runner_output(out_symbols[sym])
          
          # Add some example extensions to demonstrate flexibility
          live_data_manager.add_event({
              "time": int(time.time()),
              "type": "data_update",
              "symbol": sym,
              "candles_count": len(candles),
              "zones_count": len(zones['supportSegments']) + len(zones['resistanceSegments'])
          })
          
          # Save to file
          live_data_manager.save()
          print(f"DEBUG: Saved live data for {sym} to {live_data_manager.get_file_path()}")
          
          # Show summary
          summary = live_data_manager.get_summary()
          print(f"DEBUG: {sym} Summary - UUID: {summary['uuid']}, Candles: {summary['candles_count']}, Support Zones: {summary['support_zones_count']}, Resistance Zones: {summary['resistance_zones_count']}")
        else:
          print(f"DEBUG: LiveDataManager not available for {sym}, skipping file save")

      latest_seq += 1
      snapshot = {
        'symbols': out_symbols,
        'stats': stats,
        'meta': {
          'session_dir': str(session_dir),
          'timeframe': timeframe_str,
          'symbols': symbols,
          'latest_seq': latest_seq,
          'updated_at': datetime.now(tz=timezone.utc).isoformat(),
        },
      }
      _write_json(snapshot_path, snapshot)
      _status_patch({'latest_seq': latest_seq, 'state': 'running'})

      # Broadcast chart updates via WebSocket if available
      if WEBSOCKET_BROADCAST_AVAILABLE:
        try:
          session_id = session_dir.name
          for symbol, symbol_data in out_symbols.items():
            # Format data to match frontend ChartUpdateMessage interface
            chart_update_data = {
              'symbol': symbol,
              'chartOverlayData': {
                'data': {
                  symbol: symbol_data.get('timestamp_keyed_data', {})  # Use the stored timestamp-keyed data
                },
                'trades': []  # Will be populated with live trades
              },
              'chartData': symbol_data.get('chartData', {}),
              'candles': symbol_data.get('candles', []),
              'timestamp': datetime.now(tz=timezone.utc).timestamp()
            }
            broadcast_chart_update(session_id, chart_update_data)
          print(f"DEBUG: Broadcasted chart updates for session {session_id}")
        except Exception as e:
          print(f"Warning: Failed to broadcast chart update: {e}")

      time.sleep(float(args.poll_seconds))

  except KeyboardInterrupt:
    try:
      prev = _load_json(status_path)
      _write_json(status_path, {**prev, 'state': 'stopped', 'returncode': 0})
    except Exception:
      pass
    return 0

  except Exception as e:
    tb = traceback.format_exc()
    try:
      prev = {}
      try:
        prev = _load_json(status_path)
      except Exception:
        prev = {}
      _write_json(status_path, {**prev, 'state': 'error', 'returncode': 1, 'error': str(e), 'traceback': tb})
    finally:
      print(tb, file=sys.stderr)
    return 1


if __name__ == '__main__':
  raise SystemExit(main())
