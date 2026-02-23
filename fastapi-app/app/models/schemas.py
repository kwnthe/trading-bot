from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal, Union
from datetime import datetime
from enum import Enum
import uuid


class FieldType(str, Enum):
    STR = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    DATETIME = "datetime"
    CHOICE = "choice"
    HIDDEN = "hidden"


class Destination(str, Enum):
    BACKTEST = "backtest"
    ENV = "env"
    META = "meta"


class ParamDef(BaseModel):
    name: str
    label: str
    field_type: FieldType
    destination: Destination
    required: bool = True
    group: str = "General"
    help_text: str = ""
    choices: Optional[List[tuple[str, str]]] = None
    fallback_default: Any = None


class TimeframeChoice(BaseModel):
    value: str
    label: str


class BacktestRequest(BaseModel):
    strategy: str = "break_retest"
    symbols: str
    timeframe: str
    max_candles: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    spread_pips: Optional[float] = 0.0
    
    # Environment overrides
    RR: float
    INITIAL_EQUITY: float
    RISK_PER_TRADE: float
    BREAKOUT_LOOKBACK_PERIOD: int
    ZONE_INVERSION_MARGIN_ATR: float
    BREAKOUT_MIN_STRENGTH_ATR: float
    MIN_RISK_DISTANCE_ATR: float
    SR_CANCELLATION_THRESHOLD_ATR: float
    SL_BUFFER_ATR: float
    EMA_LENGTH: int
    CHECK_FOR_DAILY_RSI: Optional[bool] = True
    BACKTEST_FETCH_CSV_URL: Optional[str] = None
    
    # Live trading (MT5)
    MT5_LOGIN: Optional[int] = None
    MT5_PASSWORD: Optional[str] = None
    MT5_SERVER: Optional[str] = None
    MT5_PATH: Optional[str] = None
    
    # Meta
    MODE: str = "backtest"
    MARKET_TYPE: str = "forex"
    
    @validator('symbols')
    def validate_symbols(cls, v):
        symbols = [s.strip() for s in v.split(",") if s.strip()]
        if not symbols:
            raise ValueError("Provide at least one symbol")
        return symbols


class LiveTradingRequest(BaseModel):
    strategy: str = "break_retest"
    symbols: str
    timeframe: str
    max_candles: Optional[int] = None
    
    # Environment overrides (optional subset)
    RR: Optional[float] = None
    INITIAL_EQUITY: Optional[float] = None
    RISK_PER_TRADE: Optional[float] = None
    BREAKOUT_LOOKBACK_PERIOD: Optional[int] = None
    ZONE_INVERSION_MARGIN_ATR: Optional[float] = None
    BREAKOUT_MIN_STRENGTH_ATR: Optional[float] = None
    MIN_RISK_DISTANCE_ATR: Optional[float] = None
    SR_CANCELLATION_THRESHOLD_ATR: Optional[float] = None
    SL_BUFFER_ATR: Optional[float] = None
    EMA_LENGTH: Optional[int] = None
    CHECK_FOR_DAILY_RSI: Optional[bool] = None
    BACKTEST_FETCH_CSV_URL: Optional[str] = None
    
    # Live trading (MT5)
    MT5_LOGIN: Optional[int] = None
    MT5_PASSWORD: Optional[str] = None
    MT5_SERVER: Optional[str] = None
    MT5_PATH: Optional[str] = None
    
    @validator('symbols')
    def validate_symbols(cls, v):
        symbols = [s.strip() for s in v.split(",") if s.strip()]
        if not symbols:
            raise ValueError("Provide at least one symbol")
        return symbols


class JobStatus(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed", "finished"]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    pid: Optional[int]
    python_executable: Optional[str]
    returncode: Optional[int]
    error: Optional[str]
    params: Optional[Dict[str, Any]]
    stdout: Optional[str]
    stderr: Optional[str]
    has_result: bool
    result_url: Optional[str]


class JobResult(BaseModel):
    job_id: str
    status: str
    result: Dict[str, Any]
    created_at: datetime
    completed_at: datetime


class LiveSessionStatus(BaseModel):
    session_id: str
    state: Literal["queued", "running", "stopped", "error"]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    pid: Optional[int]
    python_executable: Optional[str]
    returncode: Optional[int]
    error: Optional[str]
    latest_seq: Optional[int]
    params: Optional[Dict[str, Any]]
    stdout: Optional[str]
    stderr: Optional[str]
    has_snapshot: bool
    snapshot_url: Optional[str]


class LiveSessionStart(BaseModel):
    ok: bool
    session_id: str
    status_url: str
    snapshot_url: str
    stop_url: str


class LiveSessionStop(BaseModel):
    ok: bool
    killed: bool


class ActiveSession(BaseModel):
    active_session_id: Optional[str]


class Strategy(BaseModel):
    id: str
    label: str


class Preset(BaseModel):
    name: str
    values: Dict[str, Any]


class PresetList(BaseModel):
    presets: List[str]


class PresetSave(BaseModel):
    name: str
    values: Dict[str, Any]


class MarkerRequest(BaseModel):
    time: Union[int, float]
    value: Union[int, float]
    marker_type: str
    metadata: Optional[Dict[str, Any]] = {}


class LiveDataSession(BaseModel):
    uuid: str
    symbol: str
    timeframe: str
    last_updated: int
    created_at: int
    file_size: int


class LiveDataSessions(BaseModel):
    sessions: List[LiveDataSession]


class LiveDataSummary(BaseModel):
    uuid: str
    symbol: str
    timeframe: str
    last_updated: int
    candles_count: int
    support_zones_count: int
    resistance_zones_count: int
    ema_points_count: int
    markers_count: int
    breakouts_count: int
    events_count: int
    custom_indicators: List[str]
    file_size: int


class WebSocketMessage(BaseModel):
    type: str
    timestamp: Optional[str] = None
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    status: Optional[Dict[str, Any]] = None


class WebSocketResponse(BaseModel):
    type: str
    timestamp: str
    message: Optional[str] = None
    session_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    status: Optional[Dict[str, Any]] = None
    subscribed_to: Optional[List[str]] = None


# Response wrappers
class APIResponse(BaseModel):
    ok: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: str
    details: Optional[Dict[str, Any]] = None
