"""
Candlestick data model for representing OHLCV data.
"""

from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import pandas as pd
from src.utils.config import Config


class CandleType(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


@dataclass
class Candlestick:
    """
    Attributes:
        timestamp: The timestamp of the candlestick
        open: Opening price
        high: Highest price during the period
        low: Lowest price during the period
        close: Closing price
        volume: Trading volume
    """
    
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    
    def __post_init__(self):
        # Use unified validation
        data = {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }
        # TODO: Validate candlestick data
        # validate_candlestick_data(data)
    
    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)
    
    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)
    
    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low
    
    @property
    def total_range(self) -> float:
        return self.high - self.low
    
    @property
    def is_bullish(self) -> bool:
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def candle_type(self) -> CandleType:
        if self.is_bullish:
            return CandleType.BULLISH
        elif self.is_bearish:
            return CandleType.BEARISH
    
    @property
    def is_doji(self) -> bool:
        return abs(self.close - self.open) < (self.total_range * Config.doji_threshold)
    
    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Candlestick':
        return cls(
            timestamp=data['timestamp'],
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            volume=data.get('volume', 0.0)
        )
    
    def __str__(self) -> str:
        direction = "🟢" if self.is_bullish else "🔴" if self.is_bearish else "⚪"
        price_format = Config.get_price_format()
        volume_format = Config.get_volume_format()
        return (f"{direction} {self.timestamp.strftime('%Y-%m-%d %H:%M')} "
                f"O:{self.open:{price_format}} H:{self.high:{price_format}} "
                f"L:{self.low:{price_format}} C:{self.close:{price_format}} "
                f"V:{self.volume:{volume_format}}")
    
    def __repr__(self) -> str:
        return (f"Candlestick(timestamp={self.timestamp}, open={self.open}, "
                f"high={self.high}, low={self.low}, close={self.close}, volume={self.volume})")
    
    def from_bt(data, index: int) -> 'Candlestick':
        if data is None:
            raise ValueError("from_bt received data are None")
        
        # Check if we have enough data points
        if len(data.close) <= abs(index):
            raise IndexError(f"Not enough data points. Requested index {index}, but only {len(data.close)} points available")
        
        return Candlestick(
            timestamp=data.datetime.date(index),
            open=data.open[index],
            high=data.high[index],
            low=data.low[index],
            close=data.close[index],
            volume=data.volume[index] if hasattr(data, 'volume') else 0.0
        )