import backtrader as bt
import numpy as np
from indicators import Zones
from src.models.trend import Trend
from src.utils.config import Config
from src.models.candlestick import CandleType, Candlestick
from src.utils.strategy_utils.general_utils import is_minor_pair, convert_atr_to_price
from src.models.s_r import SR, SRLevelType
from src.utils.environment_variables import EnvironmentVariables

class BreakoutIndicator(Zones):
    lines = ('breakout', 'breakout_trend')
    plotinfo = dict(plot=True, subplot=False, plotmaster=None, plotabove=True, plotname='Breakout')
        
    plotlines = dict(
        breakout=dict(
            marker='o',
            markersize=8,
            color='gray',
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
        self.support = None
        self.supports: dict[int, SR] = {}
        self.resistance = None
        self.resistances: dict[int, SR] = {}
    def next(self):
        super().next()
        if self.candle_index < 3:
            return
        
        try:
            self.current_candle = Candlestick.from_bt(self.data, 0)
            self.support = self.lines.support1[0]
            self.resistance = self.lines.resistance1[0]

            self.update_sr_lists()

            self.lines.breakout[0] = float('nan')
            self.lines.breakout_trend[0] = float('nan')
            self.check_for_breakout()
        except (IndexError, ValueError) as e:
            # Handle cases where we don't have enough data
            return
    
    def update_sr_lists(self):
        if len(self.supports) == 0:
            self.supports[self.candle_index] = SR(id=self.candle_index, type=SRLevelType.SUPPORT, price=self.support, candle_index=self.candle_index)
        elif self.support != list(self.supports.values())[-1].price:
            self.supports[self.candle_index] = SR(id=self.candle_index, type=SRLevelType.SUPPORT, price=self.support, candle_index=self.candle_index)

        if len(self.resistances) == 0:
            self.resistances[self.candle_index] = SR(id=self.candle_index, type=SRLevelType.RESISTANCE, price=self.resistance, candle_index=self.candle_index)
        elif self.resistance != list(self.resistances.values())[-1].price:
            self.resistances[self.candle_index] = SR(id=self.candle_index, type=SRLevelType.RESISTANCE, price=self.resistance, candle_index=self.candle_index)

    def check_for_breakout(self):
        if self.is_breakout() == Trend.UPTREND:
            self.add_breakout_point()
            self.set_breakout_trend(Trend.UPTREND)
            self.breakout_price = self.resistance
        elif self.is_breakout() == Trend.DOWNTREND:
            self.add_breakout_point()
            self.set_breakout_trend(Trend.DOWNTREND)
            self.breakout_price = self.support

    def is_breakout(self):
        try:
            previous_candle = Candlestick.from_bt(self.data, -1)
            # Get current ATR value (inherited from Zones parent class)
            current_atr = self.atr[0] if len(self.atr) > 0 else 0.0
            min_breakout_price = convert_atr_to_price(current_atr, EnvironmentVariables.BREAKOUT_MIN_STRENGTH_ATR, self.symbol)
            
            if previous_candle.close <= self.resistance + min_breakout_price and \
                self.current_candle.close >= self.resistance + min_breakout_price:
                return Trend.UPTREND
            elif previous_candle.close >= self.support - min_breakout_price and \
                self.current_candle.close <= self.support - min_breakout_price:
                return Trend.DOWNTREND
            return None
        except (IndexError, ValueError) as e:
            return None
    def add_breakout_point(self):
        self.lines.breakout[0] = self.current_candle.close
        
    def set_breakout_trend(self, trend):
        self.last_breakout_trend = trend
        self.breakout_price = self.resistance if trend == Trend.UPTREND else self.support
        
        # Convert trend to numeric value for the line
        trend_value = trend.value if trend is not None else float('nan')
        self.lines.breakout_trend[0] = trend_value
    
    def just_broke_out(self): # return (bool, trend)
        return not np.isnan(self.lines.breakout[0]), Trend.from_value(self.lines.breakout_trend[0])
