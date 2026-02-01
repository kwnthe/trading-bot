import backtrader as bt
from src.models.trend import Trend
from src.utils.config import Config
from src.models.candlestick import CandleType, Candlestick
from src.utils.strategy_utils.general_utils import get_total_movement_from_continuous_candles, is_minor_pair, is_movement_significant
import math

sr_config = dict(color='#E91E63', linewidth=5, linestyle='-', alpha=0.8, zorder=10)
support_config = sr_config.copy()
support_config['color'] = '#2962FF'
resistance_config = sr_config.copy()
resistance_config['color'] = '#E91E63'
clear_support_after_bars = 1
clear_resistance_after_bars = 1

class Zones(bt.Indicator):
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
        # Calculate ATR for movement significance checks
        self.atr = bt.indicators.ATR(self.data, period=Config.atr_length)
        # self.addminperiod(self.lookback_period)
        
    def next(self):
        self.candle_index += 1
        if len(self.data.close) <= 1:
            return

        # Ensure we have enough data before accessing
        if len(self.data.close) < 2:
            return

        try:
            current_candle = Candlestick.from_bt(self.data, 0)
            
            # Get current ATR value (use [0] to get the current bar's value)
            current_atr = self.atr[0] if len(self.atr) > 0 else 0.0
            # Fallback to a small value if ATR is not yet calculated or is invalid
            if current_atr is None or current_atr <= 0 or (isinstance(current_atr, float) and (current_atr != current_atr)):  # Check for NaN
                current_atr = 0.0001  # Small fallback value

            continuous_movement_data = get_total_movement_from_continuous_candles(self.data, 0, self.candle_index, self.symbol, current_atr, skip_small_movements=True)
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

        if is_movement_significant(continuous_movement_high, continuous_movement_low, current_atr, self.symbol):  # Movement big enough
            # Fill the S/R lines
            # for i in range(0, last_opposite_candle_index - 1, - 1):
            for i in range(0, -1, - 1): # run one time
                if current_candle.candle_type == CandleType.BEARISH and math.isnan(self.lines.resistance1[i]):
                    self.lines.resistance1[i] = continuous_movement_high + self.sr_padding
                    if self.lines.resistance1[i] <= self.lines.support1[i]:
                        self.lines.support1[i] = float('nan')
                if current_candle.candle_type == CandleType.BULLISH and math.isnan(self.lines.support1[i]):
                    self.lines.support1[i] = continuous_movement_low - self.sr_padding
                    if self.lines.support1[i] >= self.lines.resistance1[i]:
                        self.lines.resistance1[i] = float('nan')
            
        # Extend S/R from previous bar if current bar has nan values
        # This ensures S/R levels persist across bars until new ones are detected
        # We validate to ensure support < resistance to handle weekend gaps and extreme moves
        if self.extend_srs:
            # Track which values were extended (vs set this bar)
            support_was_extended = False
            resistance_was_extended = False
            
            # Extend support if it's nan and previous support exists
            if math.isnan(self.lines.support1[0]) and not math.isnan(self.lines.support1[-1]):
                self.lines.support1[0] = self.lines.support1[-1]
                support_was_extended = True
            
            # Extend resistance if it's nan and previous resistance exists
            if math.isnan(self.lines.resistance1[0]) and not math.isnan(self.lines.resistance1[-1]):
                self.lines.resistance1[0] = self.lines.resistance1[-1]
                resistance_was_extended = True
            
            # Validate: support must be < resistance (both must be valid numbers)
            # If validation fails, clear the conflicting value to avoid invalid state
            if not math.isnan(self.lines.support1[0]) and not math.isnan(self.lines.resistance1[0]):
                if self.lines.support1[0] >= self.lines.resistance1[0]:
                    # Invalid state: support >= resistance
                    # Prefer keeping the value that was set this bar (not extended)
                    # If both were extended, clear the one further from current price
                    if support_was_extended and not resistance_was_extended:
                        # Support was extended, resistance was set this bar - clear support
                        self.lines.support1[0] = float('nan')
                    elif resistance_was_extended and not support_was_extended:
                        # Resistance was extended, support was set this bar - clear resistance
                        self.lines.resistance1[0] = float('nan')
                    else:
                        # Both were extended or both were set this bar
                        # Clear the one further from current price (less relevant)
                        current_price = self.data.close[0]
                        support_distance = abs(self.lines.support1[0] - current_price)
                        resistance_distance = abs(self.lines.resistance1[0] - current_price)
                        if support_distance > resistance_distance:
                            self.lines.support1[0] = float('nan')
                        else:
                            self.lines.resistance1[0] = float('nan')
        