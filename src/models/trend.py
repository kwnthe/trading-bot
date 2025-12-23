from enum import Enum
import math

class Trend(Enum):
    UPTREND = 1
    DOWNTREND = 2
    SIDEWAYS = 3

    def __str__(self):
        """Return a readable string representation of the trend."""
        return {
            Trend.UPTREND: "uptrend",
            Trend.DOWNTREND: "downtrend",
            Trend.SIDEWAYS: "sideways"
        }[self]

    @staticmethod
    def from_value(value):
        return Trend(value) if value is not None and not math.isnan(value) else None