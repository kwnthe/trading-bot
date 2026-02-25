#!/usr/bin/env python3
"""
Live trading runner – spawned by the FastAPI live/run endpoint.

Writes the same file artefacts the backtest runner writes so the React
frontend can consume them identically:

  session_dir/
    params.json        – written by the API before we start
    status.json        – updated every tick  (state / pid / seq / …)
    snapshot.json      – ResultJson format   (symbols / stats / meta)
    chart_overlays.json– chart overlay data  (written by ChartOverlayManager)
    stdout.log         – our stdout (managed by parent Popen)
    stderr.log         – our stderr
"""
import argparse
import importlib
import json
import os
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── path setup ──────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).parent          # fastapi-app/
_REPO_ROOT  = _SCRIPT_DIR.parent             # trading-bot/
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "src"))

# ── optional MT5 ────────────────────────────────────────────────────
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False


# ── helpers ─────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    try:
        tmp.replace(path)
    except PermissionError:
        for _ in range(5):
            time.sleep(0.05)
            try:
                tmp.replace(path)
                break
            except PermissionError:
                pass


def _flush():
    """Flush stdout/stderr so the log files are updated for the UI."""
    sys.stdout.flush()
    sys.stderr.flush()


def _to_unix_seconds(dt: datetime) -> int:
    return int(dt.timestamp())


# ── LiveRunner ──────────────────────────────────────────────────────
class LiveRunner:
    """
    Runs a live trading loop:
      1) Fetch historical candles from MT5
      2) Run the real BreakRetestStrategy via main.backtesting() so
         ChartOverlayManager writes chart_overlays.json (EMA, zones, markers)
      3) Read chart_overlays.json and build the chartOverlayData in the
         timestamp-keyed format the frontend expects
      4) Write snapshot.json + status.json every tick
    """

    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.session_id = session_dir.name
        self.running = False
        self.mt5_connected = False

        # Load params
        params_file = session_dir / "params.json"
        if params_file.exists():
            with open(params_file) as f:
                self.params = json.load(f)
        else:
            self.params = {}

        backtest_args = self.params.get("backtest_args", {})
        env_overrides = self.params.get("env_overrides", {})

        # ── Apply env_overrides BEFORE importing any strategy / Config code ──
        for k, v in env_overrides.items():
            os.environ[str(k)] = str(v)

        # Reload Config so it picks up the new env vars
        import src.utils.config as config_module
        importlib.reload(config_module)

        raw_symbols = backtest_args.get("symbols", [])
        if isinstance(raw_symbols, str):
            raw_symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]
        self.symbols: List[str] = raw_symbols or ["BTCUSD"]

        self.timeframe: str = backtest_args.get("timeframe", "H1")
        self.max_candles: int = int(backtest_args.get("max_candles") or 200)

        self.mt5_login: int = int(env_overrides.get("MT5_LOGIN", 0))
        self.mt5_password: str = env_overrides.get("MT5_PASSWORD", "")
        self.mt5_server: str = env_overrides.get("MT5_SERVER", "")

        # paths
        self.status_path  = session_dir / "status.json"
        self.snapshot_path = session_dir / "snapshot.json"
        self.overlay_path  = session_dir / "chart_overlays.json"

    # ── status helpers ──────────────────────────────────────────────
    def write_status(self, state: str, seq: int = 0, error: str = None):
        existing = {}
        if self.status_path.exists():
            try:
                with open(self.status_path) as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing.update({
            "state": state,
            "latest_seq": seq,
            "updated_at": _now_iso(),
            "session_id": self.session_id,
        })
        if error:
            existing["error"] = error
        _write_json(self.status_path, existing)

    def write_snapshot(self, symbol_data: Dict[str, Any], stats: Dict[str, Any],
                       seq: int):
        snapshot = {
            "symbols": symbol_data,
            "stats": stats,
            "meta": {
                "session_dir": str(self.session_dir),
                "timeframe": self.timeframe,
                "symbols": self.symbols,
                "latest_seq": seq,
                "updated_at": _now_iso(),
                "status": "running",
            },
        }
        _write_json(self.snapshot_path, snapshot)

    # ── MT5 ─────────────────────────────────────────────────────────
    def connect_mt5(self) -> bool:
        if not MT5_AVAILABLE:
            print("MetaTrader5 package not installed – cannot trade")
            return False
        if not self.mt5_login:
            print("No MT5_LOGIN configured – cannot trade")
            return False
        if not mt5.initialize():
            print(f"mt5.initialize() failed: {mt5.last_error()}")
            return False
        if not mt5.login(self.mt5_login, self.mt5_password, self.mt5_server):
            print(f"mt5.login() failed: {mt5.last_error()}")
            mt5.shutdown()
            return False
        print(f"Connected to MT5: {self.mt5_server}")
        self.mt5_connected = True
        return True

    def disconnect_mt5(self):
        if self.mt5_connected:
            try:
                mt5.shutdown()
            except Exception:
                pass
            self.mt5_connected = False

    def fetch_mt5_candles(self, symbol: str) -> List[Dict]:
        """Fetch OHLCV candles from MT5 for one symbol."""
        if not self.mt5_connected:
            return []
        try:
            tf = getattr(mt5, f"TIMEFRAME_{self.timeframe}", mt5.TIMEFRAME_H1)
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, self.max_candles)
            if rates is None or len(rates) == 0:
                print(f"  No candle data for {symbol}")
                return []
            candles = []
            for r in rates:
                candles.append({
                    "time":   int(r["time"]),
                    "open":   float(r["open"]),
                    "high":   float(r["high"]),
                    "low":    float(r["low"]),
                    "close":  float(r["close"]),
                    "volume": int(r["tick_volume"]),
                })
            return candles
        except Exception as e:
            print(f"  Error fetching {symbol}: {e}")
            return []

    def get_account_stats(self) -> Dict[str, Any]:
        if not self.mt5_connected:
            return {}
        try:
            info = mt5.account_info()
            if info is None:
                return {}
            return {
                "balance": info.balance,
                "equity": info.equity,
                "profit": info.profit,
                "margin": info.margin,
                "margin_free": info.margin_free,
            }
        except Exception:
            return {}

    # ── run strategy on candles (produces chart_overlays.json) ──────
    def run_strategy_on_candles(self, all_candles: Dict[str, List[Dict]]):
        """
        Feed historical candles into the real BreakRetestStrategy via
        backtrader so that BaseStrategy.sync_indicator_data_to_chart()
        populates ChartOverlayManager → chart_overlays.json.

        This is the same approach run_backtest.py uses to generate
        EMA, support/resistance zones, and markers.
        """
        import backtrader as bt
        import pandas as pd
        from src.infrastructure.ChartOverlayManager import (
            set_chart_overlay_manager_for_job,
            reset_chart_overlay_manager,
        )
        from src.utils.config import Config
        from strategies.BreakRetestStrategy import BreakRetestStrategy
        from indicators.TestIndicator import TestIndicator
        from src.brokers.ForexLeverage import ForexLeverage

        # Point the global ChartOverlayManager at our session directory
        reset_chart_overlay_manager()
        set_chart_overlay_manager_for_job(self.session_dir)

        cerebro = bt.Cerebro(stdstats=False)
        cerebro.data_indicators = {}
        cerebro.data_state = {}
        cerebro.broker.addcommissioninfo(ForexLeverage())

        first_symbol = self.symbols[0]

        # ── Add main (H1) data feeds first ──
        for symbol in self.symbols:
            candles = all_candles.get(symbol, [])
            if not candles:
                continue

            df = pd.DataFrame(candles)
            df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.rename(columns={"time": "orig_time"})

            data = bt.feeds.PandasData(
                dataname=df,
                datetime="datetime",
                open="open", high="high", low="low", close="close",
                volume="volume",
                openinterest=-1,
            )
            data._name = symbol
            cerebro.adddata(data, name=symbol)

        if not cerebro.datas:
            print("  No data feeds added – skipping strategy run")
            return

        # ── Add daily-resampled feeds for daily RSI (if enough data) ──
        # RSI(14) needs at least 15 daily bars. With limited H1 candles
        # (e.g. 200 H1 = ~8 days) we may not have enough. Check ALL
        # symbols first, then add daily feeds only if every symbol passes.
        MIN_DAILY_BARS = 15  # RSI period (14) + 1
        cerebro.daily_data_mapping = {}

        # Phase 1: build daily DataFrames and check bar counts
        daily_dfs: Dict[int, Any] = {}  # index -> (symbol, daily DataFrame)
        has_enough_daily = True
        for i, symbol in enumerate(self.symbols):
            candles = all_candles.get(symbol, [])
            if not candles:
                continue
            df = pd.DataFrame(candles)
            df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
            df = df.set_index("datetime")
            daily = df.resample("1D").agg({
                "open": "first", "high": "max",
                "low": "min", "close": "last", "volume": "sum",
            }).dropna(subset=["open"]).reset_index()
            if len(daily) < MIN_DAILY_BARS:
                print(f"  {symbol}: only {len(daily)} daily bars (need {MIN_DAILY_BARS}) – skipping daily RSI for all")
                has_enough_daily = False
                break
            daily_dfs[i] = (symbol, daily)

        # Phase 2: add daily feeds only if ALL symbols passed
        if has_enough_daily and daily_dfs:
            for i, (sym_name, daily) in daily_dfs.items():
                daily_feed = bt.feeds.PandasData(
                    dataname=daily, datetime="datetime",
                    open="open", high="high", low="low", close="close",
                    volume="volume", openinterest=-1,
                )
                daily_feed._name = f"{sym_name}_DAILY"
                cerebro.adddata(daily_feed, name=f"{sym_name}_DAILY")
                cerebro.daily_data_mapping[i] = daily_feed
        else:
            # Disable daily RSI check so strategy treats daily_rsi=None
            Config.check_for_daily_rsi = False
            print("  Daily RSI disabled (insufficient daily bars)")

        cerebro.addstrategy(BreakRetestStrategy, symbol=first_symbol, rr=Config.rr)
        cerebro.addindicator(TestIndicator)
        cerebro.broker.set_cash(Config.initial_equity)

        print(f"  Running backtrader strategy on {len(cerebro.datas)} symbol(s)…")
        _flush()

        results = cerebro.run()
        strat = results[0]

        print(f"  Strategy finished – "
              f"{len(strat.completed_trades) if hasattr(strat, 'completed_trades') else '?'} trades, "
              f"chart_overlays.json written to {self.overlay_path}")
        _flush()

    # ── read chart_overlays.json & build chartOverlayData ───────────
    def build_symbol_entry(self, symbol: str, symbol_index: int,
                           candles: List[Dict]) -> Dict[str, Any]:
        """
        Build per-symbol data in ResultJson format.
        Reads overlays from chart_overlays.json (written by strategy above)
        and transforms to the timestamp-keyed format the frontend expects –
        exactly like run_backtest.py does.
        """
        # Read chart_overlays.json
        overlays: Dict = {}
        trades: List = []
        if self.overlay_path.exists():
            try:
                with open(self.overlay_path) as f:
                    raw = json.load(f)
                overlays = raw.get("overlays", {})
                trades = raw.get("trades", [])
            except Exception as e:
                print(f"  Warning: could not read chart_overlays.json: {e}")

        # Transform: {timestamp: {data_feed_index: {ema/support/resistance: val}}}
        # to:        {symbol: {timestamp: {ema/support/resistance: val}}}
        new_data: Dict[str, Dict[str, Any]] = {}
        for timestamp, feed_data in overlays.items():
            if isinstance(feed_data, dict):
                # feed_data is keyed by data_feed_index (int stored as str)
                values = feed_data.get(str(symbol_index)) or feed_data.get(symbol_index)
                if values and isinstance(values, dict):
                    new_data[str(timestamp)] = values

        # Organize trades for this symbol using their data_index field
        trades_by_feed: Dict[int, List] = {}
        for trade in trades:
            if trade.get("symbol") == symbol:
                idx = trade.get("data_index", symbol_index)  # Use data_index if available
                if idx not in trades_by_feed:
                    trades_by_feed[idx] = []
                trades_by_feed[idx].append(trade)

        # Filter trades for this symbol only
        symbol_trades = [t for t in trades if t.get("symbol") == symbol]

        return {
            "candles": candles,
            "chartOverlayData": {
                "data": {symbol: new_data},
                "trades": trades_by_feed,
            },
            "orderBoxes": [],
            "trades": symbol_trades,
        }

    # ── main loop ───────────────────────────────────────────────────
    def run(self):
        print("=" * 60)
        print(f"=== Live runner started ===")
        print(f"Session   : {self.session_id}")
        print(f"Symbols   : {self.symbols}")
        print(f"Timeframe : {self.timeframe}")
        print(f"Max candles: {self.max_candles}")
        print(f"MT5 available: {MT5_AVAILABLE}")
        print("=" * 60)
        _flush()

        self.running = True
        seq = 0

        # Write initial empty snapshot
        self.write_snapshot({}, {}, 0)
        self.write_status("running", 0)

        # Connect to MT5
        mt5_ok = self.connect_mt5()
        if not mt5_ok:
            print("MT5 not available – will keep retrying every 30s")
            _flush()

        try:
            while self.running:
                seq += 1
                tick_start = time.time()

                # Retry MT5 if disconnected
                if not self.mt5_connected:
                    mt5_ok = self.connect_mt5()
                    if mt5_ok:
                        print(f"[seq {seq}] MT5 reconnected!")
                    _flush()

                # ── Fetch candles for all symbols ──
                all_candles: Dict[str, List[Dict]] = {}
                for sym in self.symbols:
                    if self.mt5_connected:
                        all_candles[sym] = self.fetch_mt5_candles(sym)
                    else:
                        all_candles[sym] = []

                total_candles = sum(len(c) for c in all_candles.values())

                # ── Run the real strategy to generate chart_overlays.json ──
                if total_candles > 0:
                    try:
                        self.run_strategy_on_candles(all_candles)
                    except Exception as e:
                        print(f"  Strategy run error: {e}")
                        traceback.print_exc()
                        _flush()

                # ── Build snapshot with overlay data from chart_overlays.json ──
                symbol_data: Dict[str, Any] = {}
                for i, sym in enumerate(self.symbols):
                    candles = all_candles.get(sym, [])
                    if candles:
                        symbol_data[sym] = self.build_symbol_entry(sym, i, candles)
                    else:
                        symbol_data[sym] = {"candles": []}

                stats = self.get_account_stats()

                # Write snapshot + status
                self.write_snapshot(symbol_data, stats, seq)
                self.write_status("running", seq)

                elapsed = time.time() - tick_start
                print(f"[seq {seq}] tick {elapsed:.1f}s – "
                      f"{total_candles} candles – "
                      f"MT5={'ok' if self.mt5_connected else 'disconnected'}")
                _flush()

                # Sleep until next tick
                sleep_time = 30 if not self.mt5_connected else 60
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("Stopped by user (SIGINT)")
        except Exception as e:
            print(f"Fatal error: {e}")
            traceback.print_exc()
            self.write_status("error", seq, error=str(e))
        finally:
            self.running = False
            self.disconnect_mt5()
            self.write_status("stopped", seq)
            print("=== Live runner stopped ===")
            _flush()


# ── entry point ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Run live trading session")
    parser.add_argument("--session-dir", required=True,
                        help="Session directory (contains params.json)")
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        print(f"Error: session dir does not exist: {session_dir}")
        sys.exit(1)

    runner = LiveRunner(session_dir)

    # Handle SIGTERM gracefully
    def handle_sigterm(signum, frame):
        print("Received SIGTERM, shutting down…")
        runner.running = False

    signal.signal(signal.SIGTERM, handle_sigterm)

    runner.run()


if __name__ == "__main__":
    main()
