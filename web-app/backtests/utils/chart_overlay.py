"""
Chart overlay data extraction utilities for backtesting results.
"""

import math
import os
from typing import Any, Dict, List

import numpy as np
import pandas as pd


def _to_unix_seconds(dt) -> float:
    """Convert datetime to unix timestamp seconds."""
    if hasattr(dt, "timestamp"):
        return dt.timestamp()
    return dt


def _segments_from_constant_levels(times: List[float], levels: List[float]) -> List[Dict[str, Any]]:
    """Convert constant levels to line segments for chart rendering."""
    segments = []
    if len(times) < 2 or len(levels) < 2:
        return segments
    
    # Find contiguous segments of the same level
    current_level = None
    start_idx = None
    
    for i, level in enumerate(levels):
        if not isinstance(level, (int, float)) or (isinstance(level, float) and math.isnan(level)):
            # End current segment if we were in one
            if current_level is not None and start_idx is not None and i > start_idx + 1:
                segments.append({
                    "startTime": times[start_idx],
                    "endTime": times[i - 1],
                    "value": current_level
                })
            current_level = None
            start_idx = None
            continue
        
        if current_level is None:
            # Start new segment
            current_level = level
            start_idx = i
        elif abs(level - current_level) > 1e-10:  # Level changed
            # End current segment
            if i > start_idx + 1:
                segments.append({
                    "startTime": times[start_idx],
                    "endTime": times[i - 1],
                    "value": current_level
                })
            # Start new segment
            current_level = level
            start_idx = i
    
    # Handle final segment
    if current_level is not None and start_idx is not None and len(levels) > start_idx + 1:
        segments.append({
            "startTime": times[start_idx],
            "endTime": times[-1],
            "value": current_level
        })
    
    return segments


def generate_chart_overlay_data(cerebro, symbol_index: int, times: List[float], df: pd.DataFrame) -> Dict[str, Any]:
    """
    Extract chart overlay data from cerebro object for a specific symbol.
    
    Args:
        cerebro: The backtrader cerebro object containing strategy and indicators
        symbol_index: Index of the symbol being processed
        times: List of unix timestamps for candle data
        df: DataFrame containing OHLC data
        
    Returns:
        Dictionary containing ema, zones, markers, order_boxes, and trades data
        with minimal styling information - the React component will handle styling.
    """
    # EMA (compute per-symbol from candle closes)
    ema_series: List[Dict[str, Any]] = []
    try:
        ema_len = int(os.environ.get("EMA_LENGTH") or 0)
    except Exception:
        ema_len = 0
    
    if ema_len and ema_len > 0:
        # Use pandas EWM to match standard EMA behavior
        ema_vals = pd.Series(df["close"].astype(float)).ewm(span=ema_len, adjust=False).mean().to_list()
        for i, val in enumerate(ema_vals):
            if val is None or (isinstance(val, float) and math.isnan(val)):
                continue
            ema_series.append({"time": times[i], "value": float(val)})

    # Zones (support/resistance segments)
    zones = {"supportSegments": [], "resistanceSegments": []}
    try:
        if hasattr(cerebro, "data_indicators"):
            indicators = cerebro.data_indicators.get(symbol_index)
            breakout = indicators.get("breakout") if indicators else None
            if breakout is not None:
                res_vals = np.asarray(breakout.lines.resistance1.array, dtype=float)
                sup_vals = np.asarray(breakout.lines.support1.array, dtype=float)
                zones["resistanceSegments"] = _segments_from_constant_levels(times, res_vals.tolist())
                zones["supportSegments"] = _segments_from_constant_levels(times, sup_vals.tolist())
    except Exception:
        # Non-fatal; keep chart usable even if zones extraction fails.
        zones = {"supportSegments": [], "resistanceSegments": []}

    # Trades / markers / order boxes
    trades: List[Dict[str, Any]] = []
    markers: List[Dict[str, Any]] = []
    order_boxes: List[Dict[str, Any]] = []
    
    try:
        # Extract strategy from cerebro
        strat = None
        if hasattr(cerebro, '_strats'):
            for strat_list in cerebro._strats:
                if strat_list and len(strat_list) > 0:
                    strat = strat_list[0]
                    break
        
        if strat is not None and hasattr(strat, "get_completed_trades"):
            trades_all = strat.get_completed_trades()
            # Filter trades for this symbol - we'll need symbol info from trades
            trades = trades_all  # Let the calling code handle symbol filtering

            for t in trades:
                # Entry marker
                dt = t.get("open_datetime") or t.get("placed_datetime")
                if not dt:
                    continue
                if hasattr(dt, "to_pydatetime"):
                    dt = dt.to_pydatetime()
                ts = _to_unix_seconds(dt)
                side = str(t.get("order_side") or t.get("side") or "").upper()
                is_buy = "SELL" not in side
                
                # Store marker type instead of styling
                markers.append({
                    "time": ts,
                    "type": "entry",
                    "direction": "buy" if is_buy else "sell"
                })

                # Exit marker (TP/SL)
                close_reason = str(t.get("close_reason") or "")
                close_dt = t.get("close_datetime")
                if close_dt and close_reason in {"TP", "SL"}:
                    if hasattr(close_dt, "to_pydatetime"):
                        close_dt = close_dt.to_pydatetime()
                    close_ts = _to_unix_seconds(close_dt)
                    
                    markers.append({
                        "time": close_ts,
                        "type": "exit",
                        "reason": close_reason.lower()  # "tp" or "sl"
                    })

                # Order boxes (SL / TP zones)
                open_dt = t.get("open_datetime") or t.get("placed_datetime")
                close_dt = t.get("close_datetime") or open_dt
                if not open_dt:
                    continue
                if hasattr(open_dt, "to_pydatetime"):
                    open_dt = open_dt.to_pydatetime()
                if hasattr(close_dt, "to_pydatetime"):
                    close_dt = close_dt.to_pydatetime()
                    
                open_ts = _to_unix_seconds(open_dt)
                close_ts = _to_unix_seconds(close_dt)
                
                entry = float(t.get("entry_price") or t.get("entry") or 0)
                sl = float(t.get("sl") or 0)
                tp = float(t.get("tp") or 0)
                close_reason = str(t.get("close_reason") or "")
                
                if entry and sl and tp:
                    order_boxes.append({
                        "openTime": open_ts,
                        "closeTime": close_ts,
                        "entry": entry,
                        "sl": sl,
                        "tp": tp,
                        "closeReason": close_reason
                    })
                    
    except Exception:
        trades = []
        markers = []
        order_boxes = []

    return {
        "ema": ema_series,
        "zones": zones,
        "markers": markers,
        "orderBoxes": order_boxes,
        "trades": trades,
    }
