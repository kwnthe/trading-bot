import backtrader as bt
from src.models.trend import Trend
from src.utils.config import Config
from src.models.candlestick import CandleType, Candlestick
from src.utils.strategy_utils.general_utils import convert_micropips_to_price, get_total_movement_from_continuous_candles, is_minor_pair

class TestIndicator(bt.Indicator):
    lines = ('test1', 'test2', 'arrow')
    plotinfo = dict(plot=True, subplot=False, plotmaster=None, plotabove=True, plotname='Test')
    plotlines = dict(
        test1=dict(marker='o', markersize=8, color='blue', fillstyle='full', alpha=1),
        test2=dict(marker='o', markersize=8, color='#2962FF', fillstyle='full', alpha=1),
        arrow=dict(marker='^', markersize=10, color='#fcba03', fillstyle='full', alpha=1),
    )
    test1 = None
    test2 = None
    padding = 0.00001
    candle_index = -1

    def __init__(self):
        pass
    
    def next(self):
        self.candle_index += 1
        if len(self.data.close) == 1:
            return
        n_candle_index = None
        n_candle_index2 = None

        if self.candle_index == n_candle_index:
            self.lines.test1[0] = self.data.close[0]
        if self.candle_index == n_candle_index2:
            self.lines.test2[0] = self.data.open[0]
        
        # Add yellow arrow every 10 candles
        if self.candle_index > 0 and self.candle_index % 10 == 0:
            self.lines.arrow[0] = self.data.close[0]*0.998

