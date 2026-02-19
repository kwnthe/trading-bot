from src.models.timeframe import Timeframe
from datetime import datetime
import sys
import os
from pathlib import Path
import pandas as pd
from typing import Literal
from src.utils.config import Config

# Ensure root directory is in path for data.fetch import
_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

# Platform-specific imports
if sys.platform == "win32":
    import MetaTrader5 as mt5
    from data.fetch import fetch_candles
else:
    # On Mac/Linux, use remote server to fetch data
    # Use absolute import since we're in src/utils
    import sys
    import os
    project_root = os.path.dirname(_root_dir) if os.path.basename(_root_dir) == 'src' else _root_dir
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    # Ensure we can import from data directory
    data_path = os.path.join(project_root, 'data')
    if data_path not in sys.path:
        sys.path.insert(0, data_path)
    from fetch_client import fetch_from_server

# Import CSV filename generator from fetch_constants
from data.fetch_constants import generate_csv_filename as _generate_csv_filename_base


def _is_valid_ohlc_csv(file_path: Path) -> bool:
    """Check if CSV file contains valid OHLC (candlestick) data."""
    try:
        # Read just the header to check columns
        df = pd.read_csv(file_path, nrows=0)
        required_columns = ['time', 'open', 'high', 'low', 'close']
        # Check for required columns or their alternatives
        has_time = any(col in df.columns for col in ['time', 'datetime', 'timestamp', 'date'])
        has_ohlc = all(
            any(col in df.columns for col in [req, req.capitalize(), req.upper()])
            for req in ['open', 'high', 'low', 'close']
        )
        return has_time and has_ohlc
    except Exception:
        return False


def prepare_backtesting(symbols: list[str], timeframe: Timeframe, start_date: datetime, end_date: datetime):
    symbols_list = []
    for symbol in symbols:
        file_path = generate_csv_filename(symbol, timeframe, start_date, end_date)
        
        print(f"file_path: {file_path}")
        # Check if file exists AND has valid OHLC format
        if os.path.exists(file_path) and _is_valid_ohlc_csv(file_path):
            print(f"Using cached candlestick data for {symbol}")
            symbols_list.append({
                "symbol": symbol,
                "csv_file": str(file_path)
            })
            continue
        elif os.path.exists(file_path):
            # File exists but doesn't have OHLC format - skip cache and fetch new data
            print(f"Warning: Cached file {file_path.name} exists but doesn't contain OHLC data. Fetching new data...")
        
        # Fetch data based on platform
        if sys.platform == "win32":
            # Windows: Use local MetaTrader5
            TIMEFRAME_TO_MT5 = {
                Timeframe.M1: mt5.TIMEFRAME_M1,
                Timeframe.M5: mt5.TIMEFRAME_M5,
                Timeframe.M15: mt5.TIMEFRAME_M15,
                Timeframe.M30: mt5.TIMEFRAME_M30,
                Timeframe.H1: mt5.TIMEFRAME_H1,
                Timeframe.H4: mt5.TIMEFRAME_H4,
                Timeframe.D1: mt5.TIMEFRAME_D1,
            }
            mt5_timeframe = TIMEFRAME_TO_MT5[timeframe]
            res = fetch_candles("csv", start_date, end_date, symbol, mt5_timeframe)
            if res is None:
                raise ValueError(f"Failed to fetch candles for {symbol}")
            csv_path = res["path"]
        else:
            # Mac/Linux: Use remote server
            server_url = Config.backtest_fetch_csv_url or os.getenv("FETCH_SERVER_URL", "http://192.168.1.22:5000")
            if not server_url.startswith("http"):
                server_url = f"http://{server_url}"
            
            # Convert Timeframe enum to string (e.g., Timeframe.H1 -> "H1")
            timeframe_str = str(timeframe)
            
            # Format dates for API (YYYY-MM-DD HH:MM)
            start_str = start_date.strftime("%Y-%m-%d %H:%M")
            end_str = end_date.strftime("%Y-%m-%d %H:%M")
            
            print(f"Fetching {symbol} data from remote server at {server_url}...")
            try:
                csv_path = fetch_from_server(
                    server_url=server_url,
                    symbol=symbol,
                    timeframe=timeframe_str,
                    start=start_str,
                    end=end_str,
                    output_path=str(file_path)
                )
            except Exception as e:
                raise RuntimeError(f"Failed to fetch {symbol} from remote server: {e}")
        
        symbols_list.append({
            "symbol": symbol,
            "csv_file": str(csv_path)
        })
    return symbols_list

def generate_csv_filename(symbol: str, timeframe: Timeframe, start_date: datetime, end_date: datetime, type_: Literal["data", "results"] = "data"):
    """Generate CSV filename using fetch_constants function, with path and symbol formatting."""
    # Format symbol (add . if not present)
    symbol_formatted = symbol if symbol.endswith('.') else f"{symbol}."
    # Convert Timeframe enum to string
    timeframe_str = str(timeframe)
    # Use the base function from fetch_constants
    filename = _generate_csv_filename_base(symbol_formatted, timeframe_str, start_date, end_date)
    # Add the full path
    cwd = Path.cwd()
    return cwd / "data/backtests" / type_ / filename