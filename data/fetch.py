import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

from src.models.timeframe import Timeframe

# Import non-MT5 constants and utilities
# Try relative import first (when used as module), then absolute (when run as script)
try:
    from .fetch_constants import (
        DEFAULT_SYMBOL,
        DEFAULT_MODE,
        DEFAULT_START,
        DEFAULT_END,
        SCRIPT_DIR,
        generate_csv_filename,
        parse_datetime,
    )
except ImportError:
    # If relative import fails, try absolute import (for script execution)
    # Add the data directory to path if needed
    _data_dir = Path(__file__).resolve().parent
    if str(_data_dir) not in sys.path:
        sys.path.insert(0, str(_data_dir))
    from fetch_constants import (
        DEFAULT_SYMBOL,
        DEFAULT_MODE,
        DEFAULT_START,
        DEFAULT_END,
        SCRIPT_DIR,
        generate_csv_filename,
        parse_datetime,
    )

# Example invocation:
# python fetch_mt5.py \
#   --symbol GBPAUD \
#   --timeframe H1 \
#   --start "2025-12-01 00:00" \
#   --end "2025-12-16 23:59" \


# ============================================================================
# MT5 TIMEFRAME MAPPING (maps string timeframes to MT5 constants)
# ============================================================================
TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}

DEFAULT_TIMEFRAME = mt5.TIMEFRAME_H1

def get_timeframe_string(timeframe):
    """Convert MT5 timeframe constant to string representation."""
    # Create reverse mapping
    reverse_map = {v: k for k, v in TIMEFRAME_MAP.items()}
    return reverse_map.get(timeframe, "H1")  # Default to H1 if not found


# ============================================================================
# SYMBOL HANDLING
# ============================================================================
def find_correct_symbol(symbol: str):
    if mt5.symbol_info(symbol) is not None:
        return symbol

    if mt5.symbol_info(symbol + ".") is not None:
        return symbol + "."

    if symbol.endswith("."):
        if mt5.symbol_info(symbol[:-1]) is not None:
            return symbol[:-1]

    return None

# ============================================================================
# FETCH CANDLES
# ============================================================================
def fetch_candles(mode, start, end, symbol, timeframe, type_: str = "data"):
    if not mt5.initialize():
        raise RuntimeError("MT5 initialization failed")

    symbol_found = find_correct_symbol(symbol)
    if symbol_found is None:
        mt5.shutdown()
        raise ValueError(f"Symbol {symbol} not found in MT5")

    symbol = symbol_found
    symbol_info = mt5.symbol_info(symbol)

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            mt5.shutdown()
            raise RuntimeError(f"Failed to select symbol {symbol}")

    # Normalize timezone-awareness to avoid comparisons between offset-naive and offset-aware datetimes.
    if (start.tzinfo is None) != (end.tzinfo is None):
        if start.tzinfo is None:
            start = start.replace(tzinfo=end.tzinfo)
        else:
            end = end.replace(tzinfo=start.tzinfo)
    elif start.tzinfo is not None and end.tzinfo is not None and start.tzinfo != end.tzinfo:
        end = end.astimezone(start.tzinfo)

    
    if start >= end:
        mt5.shutdown()
        raise ValueError("Start time must be before end time")

    MAX_CHUNK_DAYS = 180
    date_range_days = (end - start).days
    all_rates = []

    if date_range_days > MAX_CHUNK_DAYS:
        current_start = start
        while current_start < end:
            current_end = min(current_start + timedelta(days=MAX_CHUNK_DAYS), end)
            rates = mt5.copy_rates_range(symbol, timeframe, current_start, current_end)
            if rates is not None and len(rates) > 0:
                all_rates.append(rates)
            current_start = current_end

        if not all_rates:
            mt5.shutdown()
            raise RuntimeError("No data returned")

        rates = np.concatenate(all_rates)
        rates = np.sort(rates, order="time")
    else:
        rates = mt5.copy_rates_range(symbol, timeframe, start, end)

    if rates is None or len(rates) == 0:
        mt5.shutdown()
        raise RuntimeError("MT5 returned no data")

    mt5.shutdown()

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    if mode == "csv":
        # Lazy import to avoid circular dependency
        from src.utils.backtesting import generate_csv_filename as generate_csv_filename_backtest
        tf = get_timeframe_string(timeframe)
        # Use generate_csv_filename from backtesting.py which handles path and symbol formatting
        timeframe_enum = Timeframe.from_value(tf)
        if timeframe_enum is None:
            raise ValueError(f"Invalid timeframe: {tf}")
        output_path = generate_csv_filename_backtest(symbol, timeframe_enum, start, end, type_="data")
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        return {
            "success": True,
            "path": output_path,
            "count": len(df),
        }

    return df


# ============================================================================
# CLI
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Fetch MT5 historical candles (defaults preserved)"
    )

    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        help=f"Trading symbol (default: {DEFAULT_SYMBOL})",
    )

    parser.add_argument(
        "--timeframe",
        choices=list(TIMEFRAME_MAP.keys()),
        default="H1",
        help="Timeframe (default: H1)",
    )

    parser.add_argument(
        "--start",
        type=parse_datetime,
        default=DEFAULT_START,
        help=f"Start datetime (default: {DEFAULT_START})",
    )

    parser.add_argument(
        "--end",
        type=parse_datetime,
        default=DEFAULT_END,
        help=f"End datetime (default: {DEFAULT_END})",
    )

    parser.add_argument(
        "--mode",
        choices=["csv", "return"],
        default=DEFAULT_MODE,
        help="Output mode (default: csv)",
    )

    args = parser.parse_args()

    result = fetch_candles(
        mode=args.mode,
        start=args.start,
        end=args.end,
        symbol=args.symbol,
        timeframe=TIMEFRAME_MAP[args.timeframe],
    )

    if args.mode == "csv":
        print(result)
    elif args.mode == "return":
        print(result.head())

# ============================================================================
# ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    main()
