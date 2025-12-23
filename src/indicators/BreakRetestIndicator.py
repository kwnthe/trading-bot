import backtrader as bt
from indicators import SupportResistances
from .BreakoutIndicator import BreakoutIndicator
from src.models.trend import Trend
from src.utils.config import Config
from src.models.candlestick import CandleType, Candlestick
from src.utils.strategy_utils.general_utils import convert_micropips_to_price, get_total_movement_from_continuous_candles, is_minor_pair

class BreakRetestIndicator(SupportResistances):
    lines = ('breakout', 'retest')
    plotinfo = dict(plot=True, subplot=False, plotmaster=None, plotabove=True, plotname='Break/Retest')
        
    plotlines = dict(
        breakout=dict(
            marker='o',
            markersize=8,
            color='gray',
            fillstyle='full',
            alpha=1
        ),
        retest=dict(
            marker='o', 
            markersize=8,
            color='purple',
            fillstyle='full',
            alpha=1
        )
    )

    def __init__(self, *args, symbol: str, **kwargs):
        super().__init__(*args, symbol=symbol, **kwargs)
        self.symbol = symbol
        self.candle_index = -1
        self.is_minor = is_minor_pair(symbol)
        
        # Breakout/Retest related
        self.last_breakout_trend = None
        self.breakout_price = None
        self.current_candle = None
        self.current_support = None
        self.current_resistance = None

    def next(self):
        super().next()
        if self.candle_index < 3:
            return
        self.current_candle = Candlestick.from_bt(self.data, 0)
        self.current_support = self.lines.support1[0]
        self.current_resistance = self.lines.resistance1[0]

        self.lines.breakout[0] = float('nan')
        self.lines.retest[0] = float('nan')


    def add_breakout_point(self):
        padding = self.point_padding_percentage if self.current_candle.candle_type == CandleType.BULLISH else -self.point_padding_percentage
        self.lines.breakout[0] = self.current_candle.close*(1 + padding)
    def add_retest_point(self): 
        padding = self.point_padding_percentage if self.current_candle.candle_type == CandleType.BULLISH else -self.point_padding_percentage
        self.lines.retest[0] = self.current_candle.close*(1 + padding)

    def update_resistance(self, value):
        self.current_resistance = value
        self.lines.resistance1[0] = value

    def update_support(self, value):
        self.current_support = value
        self.lines.support1[0] = value
        

