from src.models.trend import Trend
from src.utils.config import Config

class RSIConfirmations:
    @staticmethod
    def is_overbought(rsi: float) -> bool:
        return rsi > 70

    @staticmethod
    def is_oversold(rsi: float) -> bool:
        return rsi < 30

    @staticmethod
    def daily_rsi_allows_trade(rsi: float, trend: Trend) -> bool:
        if trend == Trend.UPTREND:
            return not RSIConfirmations.is_overbought(rsi)
        if trend == Trend.DOWNTREND:
            return not RSIConfirmations.is_oversold(rsi)
        return True