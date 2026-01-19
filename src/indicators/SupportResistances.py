import backtrader as bt
from src.models.trend import Trend
from src.utils.config import Config
from src.models.candlestick import CandleType, Candlestick
from src.utils.strategy_utils.general_utils import convert_micropips_to_price, get_total_movement_from_continuous_candles, is_minor_pair
import math
from src.utils.environment_variables import EnvironmentVariables

sr_config = dict(color='#E91E63', linewidth=5, linestyle='-', alpha=0.8, zorder=10)
support_config = sr_config.copy()
support_config['color'] = '#2962FF'
resistance_config = sr_config.copy()
resistance_config['color'] = '#E91E63'
clear_support_after_bars = 1
clear_resistance_after_bars = 1

class SupportResistances(bt.Indicator):
    lines = ('resistance1', 'support1')
    plotinfo = dict(plot=True, subplot=False, plotmaster=None, plotabove=True, plotname='Support/Resistance')
    plotlines = dict(
        resistance1=resistance_config,
        support1=support_config,
    )
    support1 = None
    resistance1 = None
    sr_padding = 0.00001
    candle_index = -1
    is_minor = False

    def __init__(self, *args, symbol: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.lookback_period = Config.breakout_lookback_period
        self.is_minor = is_minor_pair(symbol)
        self.extend_srs = True
        # self.addminperiod(self.lookback_period)
        
    def next(self):
        self.candle_index += 1
        if len(self.data.close) <= 1:
            return

        # Ensure we have enough data before accessing
        if len(self.data.close) < 2:
            return

        try:
            previous_candle = Candlestick.from_bt(self.data, -1)
            current_candle = Candlestick.from_bt(self.data, 0)

            continuous_movement_data = get_total_movement_from_continuous_candles(self.data, 0, self.candle_index, self.symbol, skip_small_movements=True)
            continuous_movement_high = continuous_movement_data["max_price"]
            continuous_movement_low = continuous_movement_data["min_price"]
            last_opposite_candle_index = continuous_movement_data["current_index"]
            
            # Check if we have valid data before proceeding
            if continuous_movement_high is None or continuous_movement_low is None:
                return
                
            # Check bounds before accessing last_opposite_candle
            if len(self.data.close) <= abs(last_opposite_candle_index):
                return
                
            last_opposite_candle = Candlestick.from_bt(self.data, last_opposite_candle_index)
        except (IndexError, ValueError) as e:
            # Handle cases where we don't have enough data
            return

        if (continuous_movement_high - continuous_movement_low) >= convert_micropips_to_price(EnvironmentVariables.access_config_value(EnvironmentVariables.ZONE_INVERSION_MARGIN_MICROPIPS, self.symbol), self.symbol): # Movement big enough
            # Fill the S/R lines
            # for i in range(0, last_opposite_candle_index - 1, - 1):
            for i in range(0, -1, - 1): # run one time
                if current_candle.candle_type == CandleType.BEARISH and math.isnan(self.lines.resistance1[i]):
                # if current_candle.candle_type == CandleType.BEARISH:
                    self.lines.resistance1[i] = continuous_movement_high + self.sr_padding
                # elif current_candle.candle_type == CandleType.BULLISH:
                if current_candle.candle_type == CandleType.BULLISH and math.isnan(self.lines.support1[i]):
                    self.lines.support1[i] = continuous_movement_low - self.sr_padding
        # the bug is extend srs
        # TODO extend srs if we have a break
        # What we show isnt correct. we need to show the support the moment we recognize it
        if self.extend_srs:
            if math.isnan(self.lines.support1[0]) and not math.isnan(self.lines.support1[-1]):
                self.lines.support1[0] = self.lines.support1[-1]
            if math.isnan(self.lines.resistance1[0]) and not math.isnan(self.lines.resistance1[-1]):
                self.lines.resistance1[0] = self.lines.resistance1[-1]

