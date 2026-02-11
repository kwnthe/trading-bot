import pandas as pd
import webbrowser
import time
from lightweight_charts import Chart
from datetime import datetime, timedelta
import random

def generate_random_candles(
    n: int = 100,
    start_price: float = 100.0,
    timeframe_seconds: int = 60,
    volatility: float = 0.002,
):
    start_time = datetime.now() - timedelta(seconds=n * timeframe_seconds)
    candles = []
    last_close = start_price
    current_time = start_time

    for _ in range(n):
        open_price = last_close
        pct_change = random.gauss(0, volatility)
        close_price = open_price * (1 + pct_change)
        wick_size = abs(close_price - open_price) * random.uniform(0.3, 1.2)
        
        candles.append({
            "time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "open": round(open_price, 2),
            "high": round(max(open_price, close_price) + wick_size, 2),
            "low": round(min(open_price, close_price) - wick_size, 2),
            "close": round(close_price, 2),
            "volume": random.randint(50, 300),
        })
        last_close = close_price
        current_time += timedelta(seconds=timeframe_seconds)

    return pd.DataFrame(candles)

class TradingChart:
    def __init__(self, use_light_theme: bool = False):
        # We set 'toolbox=True' only if needed, as it often injects the 'None' bug
        self.chart = Chart(inner_width=1.0, inner_height=1.0)

        if use_light_theme:
            self._apply_light_theme()
        
        self.chart.legend(visible=True)

    def _apply_light_theme(self):
        # 1. Layout - Stick to basic hex strings
        self.chart.layout(
            background_color='#FFFFFF',
            text_color='#191919',
            font_size=12
        )

        # 2. Grid - Positional strings only
        self.chart.grid('#F0F3FA', '#F0F3FA')

        # 3. Candles
        self.chart.candle_style(
            up_color='#26a69a',
            down_color='#ef5350',
            wick_up_color='#26a69a',
            wick_down_color='#ef5350',
            border_up_color='#26a69a',
            border_down_color='#ef5350'
        )

        # 4. Scales - Positional strings
        self.chart.price_scale('#787B86')
        self.chart.time_scale('#787B86')

    def set_data(self, df: pd.DataFrame):
        # The library is case-sensitive: ensures columns are 'time', 'open', etc.
        df.columns = [c.lower() for c in df.columns]
        self.chart.set(df)

    def show(self):
        # On some macOS setups, show() returns None immediately if it fails to launch 
        # the window, which caused your webbrowser.open(url) 'NoneType' error.
        url = self.chart.show(block=False)
        
        if url is None:
            # Fallback for when the built-in server is being shy
            print("Chart server starting... if no window appears, check console.")
            # Give it a tiny bit of time to initialize
            time.sleep(1) 
        else:
            print(f"Chart available at: {url}")
            webbrowser.open(url)

        # Keep alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
