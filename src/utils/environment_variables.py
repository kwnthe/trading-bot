from enum import Enum
from src.utils.config import Config

class EnvironmentVariables(Enum):
    ZONE_INVERSION_MARGIN_ATR = "ZONE_INVERSION_MARGIN_ATR"
    BREAKOUT_MIN_STRENGTH_ATR = "BREAKOUT_MIN_STRENGTH_ATR"
    MIN_RISK_DISTANCE_ATR = "MIN_RISK_DISTANCE_ATR"
    SL_BUFFER_ATR = "SL_BUFFER_ATR"
    SR_CANCELLATION_THRESHOLD_ATR = "SR_CANCELLATION_THRESHOLD_ATR"

    @staticmethod
    def access_config_value(key, pair: str):
        # Handle enum members by extracting their value
        if isinstance(key, Enum):
            key_str = key.value
        else:
            key_str = str(key)
        
        # Convert to lowercase for Config attribute lookup (Pydantic attributes are lowercase)
        key_lower = key_str.lower()
        # Keep uppercase for pair_specific_config lookup
        key_upper = key_str.upper()
        
        pair_specific_config = Config.pair_specific_config.get(pair, {})
        return pair_specific_config.get(key_upper, None) or getattr(Config, key_lower, None)