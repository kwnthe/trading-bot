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
    
    # The key insight: we need to add the indicators to cerebro AND connect them to data_indicators
    # This ensures they're actually calculated during the run
    
    # Add the indicators to cerebro so they get calculated
    breakout_indicator = cerebro.addindicator(BreakoutIndicator, symbol=symbol)
    
    # Create a simple strategy that just runs to trigger indicator calculation
    class MinimalStrategy(bt.Strategy):
        def next(self):
            pass  # Do nothing, just run to calculate indicators
    
    cerebro.addstrategy(MinimalStrategy)
    
    print(f"DEBUG: Running cerebro to calculate indicators for {symbol}")
    
    # Run cerebro to calculate the indicators
    results = cerebro.run()
    
    print(f"DEBUG: Cerebro run completed for {symbol}, results: {len(results)}")
    
    # Now the breakout_indicator should have the calculated values
    print(f"DEBUG: Extracting from calculated indicator for {symbol}")
    
    # Extract zones exactly like the backtest does
    zones = {"supportSegments": [], "resistanceSegments": []}
    
    # Extract zones from the calculated indicator in cerebro.indicators first
    if hasattr(cerebro, 'indicators') and len(cerebro.indicators) > 0:
        print(f"DEBUG Strategy: {symbol} - Extracting from calculated cerebro.indicators")
        try:
            # Get the BreakoutIndicator we added
            indicator_tuple = cerebro.indicators[0]
            if isinstance(indicator_tuple, tuple) and len(indicator_tuple) >= 1:
                breakout_calc = indicator_tuple[0]
                print(f"DEBUG Strategy: {symbol} - calculated indicator type: {type(breakout_calc)}")
                
                if hasattr(breakout_calc, 'lines') and hasattr(breakout_calc.lines, 'resistance1'):
                    import numpy as np
                    res_vals = np.asarray(breakout_calc.lines.resistance1.array, dtype=float)
                    sup_vals = np.asarray(breakout_calc.lines.support1.array, dtype=float)
                    
                    print(f"DEBUG Strategy: {symbol} - resistance1 array length: {len(res_vals)}")
                    print(f"DEBUG Strategy: {symbol} - support1 array length: {len(sup_vals)}")
                    print(f"DEBUG Strategy: {symbol} - Sample resistance values: {res_vals[:10]}")
                    print(f"DEBUG Strategy: {symbol} - Sample support values: {sup_vals[:10]}")
                    
                    # Check if we have real values
                    if len(res_vals) > 0 and len(sup_vals) > 0 and not (np.all(np.isnan(res_vals)) and np.all(np.isnan(sup_vals))):
                        zones["resistanceSegments"] = _segments_from_constant_levels(times_s, res_vals.tolist())
                        zones["supportSegments"] = _segments_from_constant_levels(times_s, sup_vals.tolist())
                        
                        print(f"DEBUG Strategy: {symbol} - SUCCESS: Generated {len(zones['supportSegments'])} support, {len(zones['resistanceSegments'])} resistance zones from calculated BreakoutIndicator")
                        if zones['supportSegments']:
                            print(f"DEBUG Strategy: Sample support: {zones['supportSegments'][0]}")
                        if zones['resistanceSegments']:
                            print(f"DEBUG Strategy: Sample resistance: {zones['resistanceSegments'][0]}")
                        
                        return zones
                    else:
                        print(f"DEBUG Strategy: {symbol} - Calculated indicator arrays are empty or NaN")
        except Exception as e:
            print(f"Warning: calculated indicator extraction failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Fallback to data_indicators approach
    if hasattr(cerebro, 'data_indicators'):
        print(f"DEBUG Strategy: {symbol} - Extracting from data_indicators")
        print(f"DEBUG Strategy: {symbol} - data_indicators type: {type(cerebro.data_indicators)}")
        print(f"DEBUG Strategy: {symbol} - data_indicators content keys: {list(cerebro.data_indicators.keys())}")
        
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
                    
                    print(f"DEBUG Strategy: {symbol} - SUCCESS: Generated {len(zones['supportSegments'])} support, {len(zones['resistanceSegments'])} resistance zones from BreakoutIndicator")
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
    
    print(f"DEBUG Strategy: {symbol} - Falling back to enhanced zone calculation")
    return _compute_zones_fallback(times_s, highs, lows, closes, symbol, lookback)
    
  except Exception as e:
    # If strategy execution fails, use fallback
    print(f"Warning: BreakoutIndicator failed, using fallback: {e}")
    import traceback
    traceback.print_exc()
    return _compute_zones_fallback(times_s, highs, lows, closes, symbol, lookback)


def _compute_zones_fallback(times_s: list[int], highs: list[float], lows: list[float], closes: list[float], symbol: str, lookback: int) -> dict[str, Any]:
  """
  Enhanced fallback zone calculation that mimics BreakoutIndicator behavior.
  This creates realistic support and resistance zones based on price action.
  """
  if not times_s or not highs or not lows or not closes:
    return {'resistanceSegments': [], 'supportSegments': []}
  
  import numpy as np
  
  # Calculate ATR for dynamic zone spacing
  atr_values = []
  for i in range(1, len(closes)):
    tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
    atr_values.append(tr)
  
  atr_period = min(14, len(atr_values))
  current_atr = sum(atr_values[-atr_period:]) / atr_period if atr_values else (highs[0] - lows[0]) * 0.02
  
  print(f"DEBUG Fallback: {symbol} - Current ATR: {current_atr}")
  
  # Find significant swing highs and lows with their actual times
  resistance_levels = []
  support_levels = []
  
  # Use a swing detection algorithm
  swing_period = max(5, lookback // 10)  # Dynamic swing period
  
  for i in range(swing_period, len(times_s) - swing_period):
    # Check for swing high (resistance)
    is_swing_high = True
    current_high = highs[i]
    for j in range(i - swing_period, i + swing_period + 1):
      if j != i and highs[j] >= current_high:
        is_swing_high = False
        break
    
    if is_swing_high:
      # Check if this resistance is significant (based on ATR)
      recent_low = min(lows[max(0, i - swing_period):i + 1])
      if current_high - recent_low > current_atr * 0.5:  # Significant move
        resistance_levels.append((current_high, times_s[i]))  # Store level with its actual time
    
    # Check for swing low (support)
    is_swing_low = True
    current_low = lows[i]
    for j in range(i - swing_period, i + swing_period + 1):
      if j != i and lows[j] <= current_low:
        is_swing_low = False
        break
    
    if is_swing_low:
      # Check if this support is significant
      recent_high = max(highs[max(0, i - swing_period):i + 1])
      if recent_high - current_low > current_atr * 0.5:  # Significant move
        support_levels.append((current_low, times_s[i]))  # Store level with its actual time
  
  # Cluster nearby levels to avoid too many zones
  def cluster_levels(levels, atr_multiplier=0.5):
    if not levels:
      return []
    
    clustered = []
    levels.sort(key=lambda x: x[0])  # Sort by price level
    
    for level, time in levels:
      if not clustered:
        clustered.append((level, time))
      else:
        # Check if this level is far enough from the last clustered level
        if abs(level - clustered[-1][0]) > current_atr * atr_multiplier:
          clustered.append((level, time))
    
    return clustered
  
  resistance_levels = cluster_levels(resistance_levels)
  support_levels = cluster_levels(support_levels)
  
  print(f"DEBUG Fallback: {symbol} - Found {len(resistance_levels)} resistance levels, {len(support_levels)} support levels")
  
  # Convert to segments with proper time limits
  resistance_segments = []
  support_segments = []
  
  # Zone expiration time (in seconds) - zones should expire after some time
  zone_duration = lookback * 60 * 60  # lookback hours in seconds
  
  for level, detection_time in resistance_levels:
    # Create segment that starts when the level was detected and lasts for zone_duration
    resistance_segments.append({
      'startTime': detection_time,
      'endTime': min(detection_time + zone_duration, times_s[-1]),
      'value': level + 0.00001  # Small padding
    })
  
  for level, detection_time in support_levels:
    # Create segment that starts when the level was detected and lasts for zone_duration
    support_segments.append({
      'startTime': detection_time,
      'endTime': min(detection_time + zone_duration, times_s[-1]),
      'value': level - 0.00001  # Small padding
    })
  
  print(f"DEBUG Fallback: {symbol} - Generated {len(support_segments)} support, {len(resistance_segments)} resistance zones")
  if support_segments:
    print(f"DEBUG Fallback: Sample support: {support_segments[0]}")
  if resistance_segments:
    print(f"DEBUG Fallback: Sample resistance: {resistance_segments[0]}")
  
  return {
    'resistanceSegments': resistance_segments,
    'supportSegments': support_segments,
  }


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
    import MetaTrader5 as mt5

    def _status_patch(patch: dict[str, Any]) -> None:
      try:
        prev = _load_json(status_path)
      except Exception:
        prev = {}
      payload = {**prev, **patch, 'updated_at': datetime.now(tz=timezone.utc).isoformat()}
      _write_json(status_path, payload)

    _status_patch({'state': 'running', 'error': None, 'python_executable': sys.executable})

    # ---- MT5 init/login ----
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
    symbols = [s.strip() for s in symbols_raw.split(',') if s.strip()]
    if not symbols:
      raise RuntimeError('Missing MT5_SYMBOL')

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
        print(f"DEBUG: LiveDataManager available, initializing for symbols")
      else:
        print(f"DEBUG: LiveDataManager not available, skipping live data features")
      
      for sym in symbols:
        # Initialize LiveDataManager for each symbol if available
        if LiveDataManager is not None:
          live_data_managers[sym] = LiveDataManager(sym, timeframe_str)
          print(f"DEBUG: Initialized LiveDataManager for {sym} with UUID: {live_data_managers[sym].uuid}")
        
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
          'markers': [],  # Keep for backward compatibility
          'orderBoxes': [],
        }
        
        print(f"DEBUG Final: {sym} - Chart data support points: {len(chart_data['support']['points'])}")
        print(f"DEBUG Final: {sym} - Chart data resistance points: {len(chart_data['resistance']['points'])}")
        print(f"DEBUG Final: {sym} - Legacy zones support: {len(zones['supportSegments'])}")
        print(f"DEBUG Final: {sym} - Legacy zones resistance: {len(zones['resistanceSegments'])}")
        
        # Debug: Show sample zone data format
        if zones['supportSegments']:
            print(f"DEBUG Final: Sample support zone format: {zones['supportSegments'][0]}")
        if zones['resistanceSegments']:
            print(f"DEBUG Final: Sample resistance zone format: {zones['resistanceSegments'][0]}")
        
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
