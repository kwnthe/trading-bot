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

    params = _load_json(params_path)

    # Apply env overrides BEFORE importing repo code (Config loads at import time).
    for k, v in (params.get("env_overrides") or {}).items():
        os.environ[str(k)] = str(v)

    # Ensure imports resolve
    repo_root = _repo_root()
    os.chdir(repo_root)
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

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

            # EMA (compute per-symbol from candle closes)
            ema_series: list[dict[str, Any]] = []
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
                    ema_series.append({"time": times_s[i], "value": float(val)})

            # Zones (support/resistance segments)
            zones = {"supportSegments": [], "resistanceSegments": []}
            try:
                if hasattr(cerebro, "data_indicators"):
                    indicators = cerebro.data_indicators.get(symbol_index)
                    breakout = indicators.get("breakout") if indicators else None
                    if breakout is not None:
                        res_vals = np.asarray(breakout.lines.resistance1.array, dtype=float)
                        sup_vals = np.asarray(breakout.lines.support1.array, dtype=float)
                        zones["resistanceSegments"] = _segments_from_constant_levels(times_s, res_vals.tolist())
                        zones["supportSegments"] = _segments_from_constant_levels(times_s, sup_vals.tolist())
            except Exception:
                # Non-fatal; keep chart usable even if zones extraction fails.
                zones = {"supportSegments": [], "resistanceSegments": []}

            # Trades / markers
            trades: list[dict[str, Any]] = []
            markers: list[dict[str, Any]] = []
            order_boxes: list[dict[str, Any]] = []
            try:
                if strat is not None and hasattr(strat, "get_completed_trades"):
                    trades_all = strat.get_completed_trades()
                    trades = [t for t in trades_all if t.get("symbol") == symbol]

                    for t in trades:
                        dt = t.get("open_datetime") or t.get("placed_datetime")
                        if not dt:
                            continue
                        if hasattr(dt, "to_pydatetime"):
                            dt = dt.to_pydatetime()
                        ts = _to_unix_seconds(dt)
                        side = str(t.get("order_side") or t.get("side") or "").upper()
                        is_buy = "SELL" not in side
                        markers.append(
                            {
                                "time": ts,
                                "position": "belowBar" if is_buy else "aboveBar",
                                "color": "#2196F3" if is_buy else "#F23645",
                                "shape": "arrowUp" if is_buy else "arrowDown",
                                "text": "",
                            }
                        )

                        # Exit marker (TP/SL)
                        close_reason = str(t.get("close_reason") or "")
                        close_dt = t.get("close_datetime")
                        if close_dt and close_reason in {"TP", "SL"}:
                            if hasattr(close_dt, "to_pydatetime"):
                                close_dt = close_dt.to_pydatetime()
                            close_ts = _to_unix_seconds(close_dt)
                            if close_reason == "TP":
                                markers.append(
                                    {
                                        "time": close_ts,
                                        "position": "aboveBar",
                                        "color": "#089981",
                                        "shape": "circle",
                                        "text": "✓",
                                    }
                                )
                            else:
                                markers.append(
                                    {
                                        "time": close_ts,
                                        "position": "belowBar",
                                        "color": "#F23645",
                                        "shape": "circle",
                                        "text": "✗",
                                    }
                                )

                    # Order boxes (SL / TP zones)
                    for t in trades:
                        open_dt = t.get("open_datetime") or t.get("placed_datetime")
                        close_dt = t.get("close_datetime") or open_dt
                        if not open_dt:
                            continue
                        if hasattr(open_dt, "to_pydatetime"):
                            open_dt = open_dt.to_pydatetime()
                        if close_dt and hasattr(close_dt, "to_pydatetime"):
                            close_dt = close_dt.to_pydatetime()

                        open_ts = _to_unix_seconds(open_dt)
                        close_ts = _to_unix_seconds(close_dt) if close_dt else open_ts
                        if close_ts < open_ts:
                            close_ts = open_ts

                        entry_price = t.get("entry_executed_price") or t.get("entry_price")
                        stop_loss = t.get("stop_loss") or t.get("sl")
                        take_profit = t.get("take_profit") or t.get("tp")
                        if entry_price is None or stop_loss is None or take_profit is None:
                            continue

                        order_boxes.append(
                            {
                                "openTime": int(open_ts),
                                "closeTime": int(close_ts),
                                "entry": float(entry_price),
                                "sl": float(stop_loss),
                                "tp": float(take_profit),
                                "closeReason": str(t.get("close_reason") or ""),
                            }
                        )
            except Exception:
                trades = []
                markers = []
                order_boxes = []

            out_symbols[symbol] = {
                "candles": candles,
                "ema": ema_series,
                "zones": zones,
                "markers": markers,
                "orderBoxes": order_boxes,
                "trades": trades,
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

