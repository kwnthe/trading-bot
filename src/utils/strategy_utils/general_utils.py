from src.models.candlestick import Candlestick, CandleType
from src.utils.environment_variables import EnvironmentVariables

def convert_micropips_to_price(pips: float, symbol: str) -> float:
    symbol = symbol.upper()
    
    if symbol.startswith("XAU") or symbol.startswith("XAG"):
        # Metals (Gold, Silver)
        micropip_value = 0.001
    elif symbol.endswith("JPY"):
        # JPY forex pairs
        micropip_value = 0.001
    else:
        # Most other forex pairs
        micropip_value = 0.00001
    
    return pips * micropip_value


def convert_pips_to_price(pips: float, instrument_type: str = "forex") -> float:
    pip_values = {
        "forex": 0.0001,    # EUR/USD, GBP/USD, AUD/USD, etc.
        # "forex_jpy": 0.01,        # USD/JPY, EUR/JPY, etc.
        # "crypto": 0.000001,        # Most crypto pairs (5 decimal places)
        # "stock": 0.01,            # Stocks (varies, but 0.01 is common)
    }
    
    pip_value = pip_values.get(instrument_type, 0.0001)
    return pips * pip_value

def convert_atr_to_price(atr_value: float, config_key: EnvironmentVariables, symbol: str, fallback_atr: float = 0.0001) -> float:
    """
    Convert an ATR-based config value to a price threshold.
    
    This function multiplies the ATR value by the config multiplier to get the threshold in price units.
    Useful for ATR-based configs like MIN_RISK_DISTANCE_ATR, SL_BUFFER_ATR, etc.
    
    Args:
        atr_value: The current ATR (Average True Range) value
        config_key: The EnvironmentVariables enum key for the ATR multiplier config (e.g., MIN_RISK_DISTANCE_ATR)
        symbol: The trading symbol (e.g., 'EURUSD', 'XAUUSD')
        fallback_atr: Fallback ATR value if atr_value is invalid (default: 0.0001)
    
    Returns:
        The threshold in price units (ATR * multiplier)
    """
    # Validate and sanitize ATR value
    if atr_value is None or atr_value <= 0 or (isinstance(atr_value, float) and (atr_value != atr_value)):  # Check for NaN
        atr_value = fallback_atr
    
    # Get the ATR multiplier from config
    atr_multiplier = EnvironmentVariables.access_config_value(config_key, symbol)
    
    # If multiplier is None or invalid, return 0
    if atr_multiplier is None:
        return 0.0
    
    return atr_value * atr_multiplier

def is_movement_significant(movement_high: float, movement_low: float, atr_value: float, symbol: str) -> bool:
    """
    Check if a price movement is significant enough based on ZONE_INVERSION_MARGIN_ATR.
    
    Args:
        movement_high: The maximum price of the movement
        movement_low: The minimum price of the movement
        atr_value: The current ATR (Average True Range) value
        symbol: The trading symbol (e.g., 'EURUSD', 'XAUUSD')
    
    Returns:
        True if the movement is significant enough, False otherwise
    """
    movement_size = movement_high - movement_low
    threshold = convert_atr_to_price(atr_value, EnvironmentVariables.ZONE_INVERSION_MARGIN_ATR, symbol)
    return movement_size >= threshold

def get_total_movement_from_continuous_candles(bt_data, start_index: int, candle_index: int, symbol: str, atr_value: float, skip_small_movements: bool = False):
    # Input must be negative index
    # Check if we have enough data
    if len(bt_data.close) <= abs(start_index):
        return {"max_price": None, "min_price": None, "current_index": start_index}
    
    start_candle = Candlestick.from_bt(bt_data, start_index)
    min_price = min(start_candle.close, start_candle.open)
    max_price = max(start_candle.close, start_candle.open)
    current_index = start_index
    current_candle = Candlestick.from_bt(bt_data, current_index)
    opposite_candle_total_movement = None

    def reached_data_end():
        return current_index == -candle_index

    while (current_candle.candle_type == start_candle.candle_type and not reached_data_end()):
        min_price = min(min_price, current_candle.close, current_candle.open)
        max_price = max(max_price, current_candle.close, current_candle.open)
        current_index -= 1
        
        # Check bounds before accessing data
        if len(bt_data.close) <= abs(current_index):
            break
            
        current_candle = Candlestick.from_bt(bt_data, current_index)
        if current_candle.candle_type != start_candle.candle_type and skip_small_movements:
            opposite_candle_total_movement = get_total_movement_from_continuous_candles(bt_data, current_index, candle_index, symbol, atr_value, False)
            # Check if we have valid data before accessing max_price and min_price
            if opposite_candle_total_movement["max_price"] is None or opposite_candle_total_movement["min_price"] is None:
                break
            if is_movement_significant(opposite_candle_total_movement["max_price"], opposite_candle_total_movement["min_price"], atr_value, symbol):
                break
            else:
                # minor movement, continue to the index where the opposite movement started - 1
                current_index = opposite_candle_total_movement["current_index"] - 1
                if len(bt_data.close) <= abs(current_index):
                    break
                current_candle = Candlestick.from_bt(bt_data, current_index)
                min_price = min(min_price, current_candle.close, current_candle.open)
                max_price = max(max_price, current_candle.close, current_candle.open)
    if reached_data_end():
        return { "max_price": None, "min_price": None, "current_index": current_index }

    return {"max_price": max_price, "min_price": min_price, "current_index": current_index}

def is_minor_pair(symbol: str) -> bool:
    return not symbol.upper().startswith("USD") and not symbol.upper().endswith("USD")
