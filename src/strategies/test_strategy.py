"""
Mock Strategy that Always Buys - for testing purposes.
"""

import backtrader as bt

class TestStrategy(bt.Strategy):
    def __init__(self):
        pass

    def next(self):
        if len(self.data) == 1:
            # Buy on the first bar
            self.buy()
            print(f"BUY at {self.data.close[0]:.5f} on {self.data.datetime.date(0)}")
        elif len(self.data) == 10:
            # Sell on the 10th bar
            self.sell()
            print(f"SELL at {self.data.close[0]:.5f} on {self.data.datetime.date(0)}")
        elif len(self.data) == 20:
            # Buy again on the 20th bar
            self.buy()
            print(f"BUY at {self.data.close[0]:.5f} on {self.data.datetime.date(0)}")
        elif len(self.data) == 30:
            # Sell again on the 30th bar
            self.sell()
            print(f"SELL at {self.data.close[0]:.5f} on {self.data.datetime.date(0)}")