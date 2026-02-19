from enum import Enum, auto
import math

from src.utils.logging import log

class TradeState(Enum):
    PENDING = auto()
    RUNNING = auto()
    CANCELED = auto()
    SL_HIT = auto()
    TP_HIT = auto()
    
    def __str__(self):
        return self.name

class OrderType(Enum):
    STOP = auto()
    LIMIT = auto()
    MARKET = auto()

class OrderSide(Enum):
    BUY = auto()
    SELL = auto()

    @staticmethod
    def from_value(value):
        if value is None:
            return None
        # If value is already an OrderSide instance, return it
        if isinstance(value, OrderSide):
            return value
        # If value is a number, check for NaN and convert
        try:
            if math.isnan(value):
                return None
        except (TypeError, ValueError):
            # value is not a number, try to convert anyway
            pass
        try:
            return OrderSide(value)
        except (ValueError, TypeError):
            return None

def log_trade(self, state: TradeState, candle_index: int, order_side: OrderSide, additional_info: str = ''):
    emoji = ''
    if state == TradeState.RUNNING:
        emoji = '💹'
    elif state == TradeState.PENDING:
        emoji = '➡️'
    elif state == TradeState.CANCELED:
        emoji = '🚫'
    elif state == TradeState.SL_HIT:
        emoji = '❌'
    elif state == TradeState.TP_HIT:
        emoji = '🎯'
    
    log(self, f"{emoji}  {order_side.name}({candle_index}) {additional_info}")