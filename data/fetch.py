import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Example invocation:
# python fetch_mt5.py \
#   --symbol GBPAUD \
#   --timeframe H1 \
#   --start "2025-12-01 00:00" \
#   --end "2025-12-16 23:59" \


# ============================================================================
# DEFAULT CONFIGURATION (PERSISTED)
# ============================================================================
DEFAULT_SYMBOL    = "EURUSD"
DEFAULT_TIMEFRAME = mt5.TIMEFRAME_H1
DEFAULT_MODE      = "csv"
DEFAULT_START     = datetime(2025, 12, 1)
DEFAULT_END       = datetime(2025, 12, 16)

# ============================================================================
# SCRIPT DIRECTORY (ALWAYS SAVE FILES HERE)
# ============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent

# ============================================================================
# TIMEFRAME MAP
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

def get_timeframe_string(timeframe):
    """Convert MT5 timeframe constant to string representation."""
    # Create reverse mapping
    reverse_map = {v: k for k, v in TIMEFRAME_MAP.items()}
    return reverse_map.get(timeframe, "H1")  # Default to H1 if not found

def generate_csv_filename(symbol: str, timeframe, start_date: datetime, end_date: datetime):
    """Generate CSV filename from symbol, timeframe, and date range."""
    return f"{symbol}_{timeframe}_{start_date.date()}_{end_date.date()}.csv"

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
def fetch_candles(mode, start, end, symbol, timeframe):
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

    if end > datetime.now():
        end = datetime.now()

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
        tf = get_timeframe_string(timeframe)
        output_path = (
            SCRIPT_DIR
            / generate_csv_filename(symbol, tf, start, end)
        )
        df.to_csv(output_path, index=False)
        return {
            "success": True,
            "path": output_path,
            "count": len(df),
        }

    return df

# ============================================================================
# DATE PARSER
# ============================================================================
def parse_datetime(value):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(
        "Date must be YYYY-MM-DD or YYYY-MM-DD HH:MM"
    )

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
        choices=TIMEFRAME_MAP.keys(),
        default=get_timeframe_string(DEFAULT_TIMEFRAME),
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
