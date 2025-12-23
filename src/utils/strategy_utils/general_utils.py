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

def get_total_movement_from_continuous_candles(bt_data, start_index: int, candle_index: int, symbol: str, skip_small_movements: bool = False):
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
            opposite_candle_total_movement = get_total_movement_from_continuous_candles(bt_data, current_index, candle_index, symbol, False)
            # Check if we have valid data before accessing max_price and min_price
            if opposite_candle_total_movement["max_price"] is None or opposite_candle_total_movement["min_price"] is None:
                break
            if (opposite_candle_total_movement["max_price"] - opposite_candle_total_movement["min_price"]) >= convert_micropips_to_price(EnvironmentVariables.access_config_value(EnvironmentVariables.ZONE_INVERSION_MARGIN_MICROPIPS, symbol), symbol):
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
