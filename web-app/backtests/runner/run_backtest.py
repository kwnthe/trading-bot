from __future__ import annotations

import argparse
import json
import math
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from src.utils.chart_utils import prepare_chart_data_for_frontend

# Add project root to Python path for main.py imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import chart overlay utilities
from utils.chart_overlay import generate_chart_overlay_data
from src.infrastructure.ChartOverlayManager import get_chart_overlay_manager, set_chart_overlay_manager_for_job


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_root() -> Path:
    # .../web-app/backtests/runner/run_backtest.py -> runner -> backtests -> web-app -> repo root
    return Path(__file__).resolve().parents[3]


def _parse_dt_iso(s: str) -> datetime:
    # Accept ISO strings produced by Django (timezone-aware)
    return datetime.fromisoformat(s)


def _to_unix_seconds(dt: datetime) -> int:
    # lightweight-charts wants seconds timestamps
    if dt.tzinfo is None:
        return int(dt.timestamp())
    return int(dt.timestamp())


def _segments_from_constant_levels(times_s: list[int], values: list[float]) -> list[dict[str, Any]]:
    """
    Convert an array of (mostly-NaN) constant price levels into horizontal segments.
    Each segment is {startTime, endTime, value}.
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
                start_idx = i if (not is_nan(v) and price_changed) else None
    return segs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-dir", required=True)
    args = ap.parse_args()

    job_dir = Path(args.job_dir).resolve()
    params_path = job_dir / "params.json"
    status_path = job_dir / "status.json"
    result_path = job_dir / "result.json"

    # Initialize ChartOverlayManager to use the job directory
    set_chart_overlay_manager_for_job(job_dir)

    params = _load_json(params_path)

    # Apply env overrides BEFORE importing repo code (Config loads at import time).
    for k, v in (params.get("env_overrides") or {}).items():
        os.environ[str(k)] = str(v)

    # Ensure imports resolve - don't change directory, just set paths
    repo_root = _repo_root()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    
    # Add src directory to path for main.py imports (after repo root)
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.append(str(src_path))

    # Import config module and reload it after env overrides are applied
    import src.utils.config as config_module
    import importlib
    importlib.reload(config_module)
    from src.utils.config import Config

    try:
        _write_json(
            status_path,
            {
                **_load_json(status_path),
                "status": "running",
                "error": None,
                "python_executable": sys.executable,
            },
        )

        from src.models.timeframe import Timeframe
        from src.utils.plot import build_ohlc_df, extract_strategy
        import numpy as np
        import pandas as pd

        import main as main_module

        backtest_args = params.get("backtest_args") or {}
        symbols: list[str] = backtest_args["symbols"]
        timeframe = Timeframe.from_value(backtest_args["timeframe"])
        start_date = _parse_dt_iso(backtest_args["start_date"])
        end_date = _parse_dt_iso(backtest_args["end_date"])

        # Convert to actual runtime types expected by backtesting()
        backtest_args = dict(backtest_args)
        backtest_args["timeframe"] = timeframe
        backtest_args["start_date"] = start_date
        backtest_args["end_date"] = end_date
        if not backtest_args.get("max_candles"):
            backtest_args["max_candles"] = None
        if "spread_pips" in backtest_args and backtest_args["spread_pips"] is None:
            backtest_args["spread_pips"] = 0.0

        res = main_module.backtesting(**backtest_args)

        cerebro = res["cerebro"]
        data_map = res["data"]  # symbol -> backtrader data feed
        stats = res.get("stats") or {}

        strat = extract_strategy(cerebro)

        out_symbols: dict[str, Any] = {}
        for symbol_index, symbol in enumerate(symbols):
            data_feed = data_map.get(symbol)
            if data_feed is None:
                continue

            df = build_ohlc_df(data_feed)
            times_s = [_to_unix_seconds(t.to_pydatetime() if hasattr(t, "to_pydatetime") else t) for t in df["time"].tolist()]

            candles = [
                {
                    "time": times_s[i],
                    "open": float(df["open"].iloc[i]),
                    "high": float(df["high"].iloc[i]),
                    "low": float(df["low"].iloc[i]),
                    "close": float(df["close"].iloc[i]),
                }
                for i in range(len(df))
            ]

            # Get chart overlay data from ChartOverlayManager (dynamic JSON storage)
            overlay_manager = get_chart_overlay_manager()
            overlay_data = overlay_manager.get_raw_data()
            overlays = overlay_data.get('overlays', {})
            trades = overlay_data.get('trades', [])

            # Calculate actual candle duration from the data (instead of static 3600)
            if len(candles) >= 2:
                candle_duration = candles[1]["time"] - candles[0]["time"]
            else:
                candle_duration = 3600  # Fallback to 1 hour if insufficient data

            out_symbols[symbol] = {
                "candles": candles,
                "chartOverlayData": {
                    symbol: overlays.get("data", {})
                },
                "orderBoxes": [],
                "trades": trades,
            }

        # Transform the chartOverlayData to the new symbol-keyed format
        for symbol_name, symbol_index in zip(symbols, range(len(symbols))):
            new_data = {}
            
            # Convert raw format: timestamp -> data_feed_index -> values
            # to new format: symbol -> timestamp -> values
            for timestamp, feed_data in overlays.items():
                if isinstance(feed_data, dict) and symbol_index in feed_data:
                    new_data[timestamp] = feed_data[symbol_index]
            
            # Organize trades by data feed index for this symbol
            trades_by_data_feed = {}
            for trade in trades:
                # Only include trades for this symbol
                if trade.get('symbol') == symbol_name:
                    # Determine data feed index based on symbol position
                    data_feed_index = symbol_index
                    if data_feed_index not in trades_by_data_feed:
                        trades_by_data_feed[data_feed_index] = []
                    trades_by_data_feed[data_feed_index].append(trade)
            
            out_symbols[symbol_name]["chartOverlayData"] = {
                "data": {
                    symbol_name: new_data
                },
                "trades": trades_by_data_feed
            }

        payload = {
            "params": {
                "symbols": symbols,
                "timeframe": str(timeframe),
                "start_date": params.get("backtest_args", {}).get("start_date"),
                "end_date": params.get("backtest_args", {}).get("end_date"),
                "max_candles": params.get("backtest_args", {}).get("max_candles"),
                "spread_pips": params.get("backtest_args", {}).get("spread_pips"),
            },
            "stats": stats,
            "symbols": out_symbols,
        }

        _write_json(result_path, payload)
        _write_json(
            status_path,
            {
                **_load_json(status_path),
                "status": "finished",
                "returncode": 0,
                "error": None,
            },
        )
        return 0

    except Exception as e:
        tb = traceback.format_exc()
        try:
            _write_json(
                status_path,
                {
                    **_load_json(status_path),
                    "status": "failed",
                    "returncode": 1,
                    "error": str(e),
                    "traceback": tb,
                },
            )
        finally:
            # Also print traceback to stderr (captured by job stderr.log)
            print(tb, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

