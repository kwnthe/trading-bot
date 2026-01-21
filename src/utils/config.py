"""
Configuration utility for loading environment variables with Pydantic.
"""

import sys
from pydantic_settings import BaseSettings
from pydantic import Field, ValidationError
from typing import Literal, Optional

VALID_MARKET_TYPES = {"forex", "crypto", "stocks"}
VALID_TRADING_MODES = {"backtest", "live"}


class Configuration(BaseSettings):
    price_precision: int = Field(..., ge=1, le=10)
    volume_precision: int = Field(..., ge=1, le=10)
    mode: Literal["backtest", "live"]
    market_type: Literal["forex", "crypto", "stocks"]
    breakout_lookback_period: int = Field(..., ge=1, le=1000000) # Candlestick count
    breakout_micropips_threshold: float = Field(..., ge=0.1, le=10000000000.0)  # Pips needed for breakout
    sideways_trigger_candle_height_micropips: float = Field(..., ge=0.1, le=100.0)  # Candle height to trigger sideways
    zone_inversion_margin_micropips: float = Field(..., ge=0, le=10000000000.0)
    breakout_min_strength_micropips: float = Field(..., ge=0.001, le=10000000000.0)
    # Take Profit and Stop Loss settings
    take_profit_pips: float = Field(default=20.0, ge=1.0, le=1000.0)  # Take profit in pips
    stop_loss_pips: float = Field(default=10.0, ge=1.0, le=1000.0)   # Stop loss in pips
    use_tp_sl: bool = Field(default=True)  # Enable/disable TP/SL functionality
    show_debug_logs: bool = Field(default=False)

    rr: float = Field(..., ge=0, le=10000) 
    initial_equity: float = Field(..., ge=0, le=10000000000.0)
    risk_per_trade: float = Field(default=0.01, ge=0.001, le=1.0)
    sr_cancellation_threshold_micropips: float = Field(default=5.0, ge=0.0001, le=1000.0)  # Threshold in pips for cancelling orders when S/R levels change
    sl_buffer_micropips: float = Field(default=2.0, ge=0.0, le=100.0)  # Buffer in pips to add below support (BUY) or above resistance (SELL) for stop loss placement
    min_risk_distance_micropips: float = Field(default=10.0, ge=0.0, le=100.0)  # Minimum risk distance in pips for placing a trade
    pair_specific_config: dict = Field(default={})  # Pair specific configuration
    check_for_daily_rsi: bool = Field(default=True)
    
    # MetaTrader 5 credentials (optional, required for live trading with -m flag)
    mt5_login: Optional[int] = Field(default=None)  # MT5 account number
    mt5_password: Optional[str] = Field(default=None)  # MT5 password
    mt5_server: Optional[str] = Field(default=None)  # MT5 server name
    mt5_path: Optional[str] = Field(default=None)  # Path to MT5 terminal (optional, auto-detected if not provided)
    mt5_symbol: Optional[str] = Field(default=None)  # Symbol(s) to trade - comma-separated (e.g., 'AUDCHF' or 'AUDCHF,EURUSD,GBPCAD')
    mt5_timeframe: Optional[str] = Field(default='H1')  # Timeframe ('M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1')

    # Logs
    zones_log_repo: Optional[str] = Field(default=None)
    show_debug_logs: bool = Field(default=False)

    # Indicators
    ema_length: int = Field(default=9)

    # Mac remote fetching of csv data
    backtest_fetch_csv_url: Optional[str] = Field(default=None)  # URL of the fetch server

    
    class Config:
        env_file = ".env"

    # ---- Helpers ----
    def get_price_format(self) -> str:
        return f".{self.price_precision}f"

    def get_volume_format(self) -> str:
        return f".{self.volume_precision}f"


def load_config() -> Configuration:
    try:
        config = Configuration()
        config.mode = "live" if "-m" in sys.argv else "backtest"
        return config
    except ValidationError as e:
        print("❌ Configuration Error: Missing or invalid required environment variables!")
        for error in e.errors():
            field = error['loc'][0] if error['loc'] else 'unknown'
            message = error['msg']
            print(f"  - {field}: {message}")
        print("\nPlease check your .env file and ensure all required variables are set.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error loading configuration: {e}")
        sys.exit(1)


# Load configuration on import - this will exit the program if validation fails
Config = load_config()