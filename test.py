import sys
import os
from datetime import datetime
from dotenv import load_dotenv
original_stdout = sys.stdout
original_stderr = sys.stderr
# sys.stdout = open(os.devnull, 'w')
# sys.stderr = open(os.devnull, 'w')

# Load .env file - try current directory first, then parent directory
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, ".env")
if not os.path.exists(dotenv_path):
    # Try parent directory (for notebooks)
    dotenv_path = os.path.join(os.path.dirname(script_dir), ".env")
load_dotenv(dotenv_path)

# Override environment variables BEFORE importing Config
# Pydantic BaseSettings converts field names to uppercase with underscores
# os.environ['ZONE_INVERSION_MARGIN_MICROPIPS'] = '110'  # Zones Tuning
# os.environ['BREAKOUT_MIN_STRENGTH_MICROPIPS'] = '100'  # Breakout Tuning
# os.environ['MIN_RISK_DISTANCE_MICROPIPS'] = '0'

notebook_dir = os.getcwd()
if os.path.basename(notebook_dir) == "notebooks":
    parent_dir = os.path.abspath("..")
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
from src.utils.config import Config
from src.models.timeframe import Timeframe
from src.utils.plot import plotly_plot
from main import backtesting
Config.show_debug_logs = True

# Tuning
# Config.zone_inversion_margin_micropips = 0 # Zones Tuning
# Config.breakout_min_strength_micropips = 100 # Breakout Tuning: We to break at least X amount of micropips in order to consider a breakout as valid
# Config.min_risk_distance_micropips = 0 


max_candles = 300
symbols = ['GBPJPY']
timeframe = Timeframe.M15
start_date = datetime(2025, 12, 1, 13, 10, 0)
end_date = datetime(2025, 12, 21, 23, 59, 59)



results = backtesting(
        symbols=symbols,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        max_candles=max_candles
    )

cerebro = results['cerebro']
data = results['data']
stats = results['stats']

print(f"stats: {stats}")

for symbol_index, (symbol, pair_data) in enumerate(data.items()):
    plotly_plot(cerebro, pair_data, symbol, symbol_index=symbol_index)