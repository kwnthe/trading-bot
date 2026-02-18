import sys
import os
from datetime import datetime
from dotenv import load_dotenv
import multiprocessing as mp
original_stdout = sys.stdout
original_stderr = sys.stderr
# sys.stdout = open(os.devnull, 'w')
# sys.stderr = open(os.devnull, 'w')
dotenv_path = os.path.abspath(os.path.join("..", ".env"))
load_dotenv(dotenv_path)

os.environ['ZONE_INVERSION_MARGIN_ATR'] = '1'  # Zones Tuning
os.environ['BREAKOUT_MIN_STRENGTH_ATR'] = '0.2'  # Breakout Tuning
os.environ['MIN_RISK_DISTANCE_ATR'] = '0.5'
os.environ['RR'] = '2'
os.environ['CHECK_FOR_DAILY_RSI'] = 'True'
os.environ['EMA_LENGTH'] = '40'
os.environ['SR_CANCELLATION_THRESHOLD_ATR'] = '0.2'
os.environ['SL_BUFFER_ATR'] = '0.3'

notebook_dir = os.getcwd()
if os.path.basename(notebook_dir) == "notebooks":
    parent_dir = os.path.abspath("..")
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
from src.utils.config import Config
from src.models.timeframe import Timeframe
from src.utils.plot import render_tv_chart
from main import backtesting

max_candles = None
#symbols = ['XAGUSD', 'XAUUSD', 'EURUSD']
symbols = ['XAGUSD']
timeframe = Timeframe.H1
# start_date = datetime(2011, 11, 26, 13, 10, 0)
start_date = datetime(2021, 11, 26, 13, 10, 0)
# start_date = datetime(2023, 11, 26, 13, 10, 0)
# 2026-01-22_15:23
# end_date = datetime(2026, 1, 22, 15, 23, 0)
# end_date = datetime(2021, 12, 22, 15, 23, 0)
end_date = datetime.now()


def main():
    res = backtesting(
            symbols=symbols,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            max_candles=max_candles)

    for symbol_index, (symbol, pair_data) in enumerate(res['data'].items()):
        # plotly_plot(res['cerebro'], pair_data, symbol, symbol_index=symbol_index, height=1400)
        render_tv_chart(res['cerebro'], pair_data, symbol, symbol_index=symbol_index)


if __name__ == "__main__":
    # lightweight_charts starts a child process (macOS uses spawn by default),
    # so we must protect top-level code to avoid:
    # "An attempt has been made to start a new process before the current process has finished its bootstrapping phase."
    mp.freeze_support()
    main()