import sys
import os
from datetime import datetime
from dotenv import load_dotenv
original_stdout = sys.stdout
original_stderr = sys.stderr
# sys.stdout = open(os.devnull, 'w')
# sys.stderr = open(os.devnull, 'w')
dotenv_path = os.path.abspath(os.path.join("..", ".env"))
load_dotenv(dotenv_path)

os.environ['ZONE_INVERSION_MARGIN_MICROPIPS'] = '100'  # Zones Tuning
os.environ['BREAKOUT_MIN_STRENGTH_MICROPIPS'] = '100'  # Breakout Tuning
os.environ['MIN_RISK_DISTANCE_MICROPIPS'] = '0.001'
os.environ['RR'] = '2'
os.environ['CHECK_FOR_DAILY_RSI'] = 'False'

notebook_dir = os.getcwd()
if os.path.basename(notebook_dir) == "notebooks":
    parent_dir = os.path.abspath("..")
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
from src.utils.config import Config
from src.models.timeframe import Timeframe
from src.utils.plot import plotly_plot
from main import backtesting

# Tuning
# Config.zone_inversion_margin_micropips = 0 # Zones Tuning
# Config.breakout_min_strength_micropips = 100 # Breakout Tuning: We to break at least X amount of micropips in order to consider a breakout as valid
# Config.min_risk_distance_micropips = 0 


if __name__ == '__main__':
    # max_candles = None
    max_candles = 300
    #symbols = ['XAGUSD', 'XAUUSD', 'EURUSD']
    # symbols = ['XAUUSD']
    symbols = ['GBPJPY']
    timeframe = Timeframe.H1
    # start_date = datetime(2024, 11, 26, 13, 10, 0)
    # end_date = datetime(2025, 12, 26, 13, 10, 0)
    start_date = datetime(2025, 12, 1, 13, 10, 0)
    end_date = datetime(2025, 12, 26, 13, 10, 0)
    # end_date = datetime.now()
    spread_pips = 2.0
    
    
    
    # Spread values (in pips):
    # For FOREX (EURUSD, GBPUSD, etc.):
    #   - ECN broker: 1.0-1.5 pips
    #   - Standard broker: 2.0-3.0 pips
    #   - Conservative: 3.0-5.0 pips
    #
    # For METALS (XAGUSD, XAUUSD):
    #   - ECN broker: 10-20 pips (0.01-0.02 USD spread)
    #   - Standard broker: 20-30 pips (0.02-0.03 USD spread)
    #   - Conservative: 30-50 pips (0.03-0.05 USD spread)
    #
    # Note: The broker automatically detects symbol type and uses correct pip value
    
    res = backtesting(
            symbols=symbols,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            max_candles=max_candles,
            spread_pips=spread_pips)  # 20 pips for XAGUSD = 0.02 USD spread (standard broker)
    
    for symbol_index, (symbol, pair_data) in enumerate(res['data'].items()):
        plotly_plot(res['cerebro'], pair_data, symbol, symbol_index=symbol_index, height=1100)