from enum import Enum, auto
import math

class Timeframe(Enum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"

    def __str__(self):
        return {
            Timeframe.M1: "M1",
            Timeframe.M5: "M5",
            Timeframe.M15: "M15",
            Timeframe.M30: "M30",
            Timeframe.H1: "H1",
            Timeframe.H4: "H4",
            Timeframe.D1: "D1",
        }[self]

    @staticmethod
    def from_value(value):
        if value is None:
            return None
        
        # Handle string values like "H1", "M5", etc.
        if isinstance(value, str):
            value_map = {
                "M1": Timeframe.M1,
                "M5": Timeframe.M5,
                "M15": Timeframe.M15,
                "M30": Timeframe.M30,
                "H1": Timeframe.H1,
                "H4": Timeframe.H4,
                "D1": Timeframe.D1,
            }
            return value_map.get(value.upper())
        
        # Handle numeric values
        try:
            if not math.isnan(value):
                return Timeframe(value)
        except (TypeError, ValueError):
            pass
        
        return None