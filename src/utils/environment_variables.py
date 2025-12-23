from enum import Enum
from src.utils.config import Config

class EnvironmentVariables(Enum):
    ZONE_INVERSION_MARGIN_MICROPIPS = "ZONE_INVERSION_MARGIN_MICROPIPS"
    BREAKOUT_MIN_STRENGTH_MICROPIPS = "BREAKOUT_MIN_STRENGTH_MICROPIPS"
    MIN_RISK_DISTANCE_MICROPIPS = "MIN_RISK_DISTANCE_MICROPIPS"
    SL_BUFFER_MICROPIPS = "SL_BUFFER_MICROPIPS"
    SR_CANCELLATION_THRESHOLD_MICROPIPS = "SR_CANCELLATION_THRESHOLD_MICROPIPS"

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