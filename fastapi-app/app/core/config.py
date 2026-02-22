from pydantic_settings import BaseSettings
from pathlib import Path
import os
from dotenv import load_dotenv

# Load .env file from multiple possible locations
def load_env_file():
    """Load .env file from various possible locations"""
    possible_env_paths = [
        Path(__file__).resolve().parent.parent.parent / ".env",  # FastAPI app root
        Path(__file__).resolve().parent.parent.parent.parent / ".env",  # Trading bot root
        Path.cwd() / ".env",  # Current working directory
    ]
    
    for env_path in possible_env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"Loaded .env from: {env_path}")
            break
    else:
        print("No .env file found, using defaults")

# Load environment variables before defining settings
load_env_file()


class Settings(BaseSettings):
    # Basic settings
    DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-key-change-me"
    
    # Project paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    VAR_DIR: Path = BASE_DIR / "var"
    JOBS_DIR: Path = VAR_DIR / "jobs"
    LIVE_DIR: Path = VAR_DIR / "live"
    
    # Trading settings
    DEFAULT_TIMEFRAME: str = "H1"
    DEFAULT_SYMBOLS: str = "XAGUSD"
    
    # Required trading parameters (with defaults)
    PRICE_PRECISION: int = 5
    VOLUME_PRECISION: int = 2
    MODE: str = "backtest"
    MARKET_TYPE: str = "forex"
    BREAKOUT_LOOKBACK_PERIOD: int = 20
    ZONE_INVERSION_MARGIN_ATR: float = 0.5
    BREAKOUT_MIN_STRENGTH_ATR: float = 1.0
    RR: float = 2.0
    INITIAL_EQUITY: float = 10000.0
    
    # WebSocket settings
    WS_HEARTBEAT_INTERVAL: int = 30
    
    # File storage
    MAX_FILE_SIZE_MB: int = 100
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Ensure directories exist
settings.VAR_DIR.mkdir(exist_ok=True)
settings.JOBS_DIR.mkdir(exist_ok=True)
settings.LIVE_DIR.mkdir(exist_ok=True)
