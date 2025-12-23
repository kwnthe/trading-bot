from src.models.timeframe import Timeframe
from datetime import datetime
import sys
import os
from pathlib import Path
if sys.platform == "win32":
    import MetaTrader5 as mt5
    from data.fetch import fetch_candles

# Ensure root directory is in path for data.fetch import
_root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

# Map Timeframe enum to MT5 timeframe constants


def prepare_backtesting(symbols: list[str], timeframe: Timeframe, start_date: datetime, end_date: datetime):
    symbols_list = []
    for symbol in symbols:
        file_path = generate_csv_filename(symbol, timeframe, start_date, end_date)
        
        if os.path.exists(file_path): # if file already exists, return the file
            print(f"Using cached candlestick data for {symbol}")
            symbols_list.append({
                "symbol": symbol,
                "csv_file": file_path
            })
            continue
        elif sys.platform != "win32":
            print(f"Lookup for {file_path} failed. Fetching new candles isn't supported on platforms other than windows.")
            sys.exit()
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
        symbols_list.append({
            "symbol": symbol,
            "csv_file": res["path"]
        })
    return symbols_list

# TODO i have duplicate of this func
def generate_csv_filename(symbol: str, timeframe: Timeframe, start_date: datetime, end_date: datetime):
    cwd = Path.cwd()
    symbol_formatted = symbol if symbol.endswith('.') else f"{symbol}."
    return cwd / f"data/{symbol_formatted}_{timeframe}_{start_date.date()}_{end_date.date()}.csv"