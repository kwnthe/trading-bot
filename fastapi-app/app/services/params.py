from typing import List, Dict, Any
from app.models.schemas import ParamDef, FieldType, Destination, TimeframeChoice

TIMEFRAME_CHOICES: List[tuple[str, str]] = [
    ("M1", "M1"),
    ("M5", "M5"),
    ("M15", "M15"),
    ("M30", "M30"),
    ("H1", "H1"),
    ("H4", "H4"),
    ("D1", "D1"),
]

PARAM_DEFS: List[ParamDef] = [
    # ----------------------------
    # Backtesting() call parameters
    # ----------------------------
    ParamDef(
        name="symbols",
        label="Symbols (comma-separated)",
        field_type=FieldType.STR,
        destination=Destination.BACKTEST,
        required=True,
        group="Backtest",
        help_text="Example: XAGUSD,XAUUSD,EURUSD",
        fallback_default="XAGUSD",
    ),
    ParamDef(
        name="timeframe",
        label="Timeframe",
        field_type=FieldType.CHOICE,
        destination=Destination.BACKTEST,
        required=True,
        group="Backtest",
        choices=TIMEFRAME_CHOICES,
        fallback_default="H1",
    ),
    ParamDef(
        name="max_candles",
        label="Max candles",
        field_type=FieldType.INT,
        destination=Destination.BACKTEST,
        required=False,
        group="Backtest",
    ),
    ParamDef(
        name="start_date",
        label="Start date",
        field_type=FieldType.DATETIME,
        destination=Destination.BACKTEST,
        required=True,
        group="Backtest",
    ),
    ParamDef(
        name="end_date",
        label="End date",
        field_type=FieldType.DATETIME,
        destination=Destination.BACKTEST,
        required=True,
        group="Backtest",
    ),
    ParamDef(
        name="spread_pips",
        label="Spread (pips)",
        field_type=FieldType.FLOAT,
        destination=Destination.BACKTEST,
        required=False,
        group="Backtest",
        fallback_default=0.0,
    ),
    # ----------------------------
    # Env overrides (strategy tuning)
    # ----------------------------
    ParamDef(name="RR", label="RR", field_type=FieldType.FLOAT, destination=Destination.ENV, required=True, group="Env overrides"),
    ParamDef(name="INITIAL_EQUITY", label="Initial equity", field_type=FieldType.FLOAT, destination=Destination.ENV, required=True, group="Env overrides"),
    ParamDef(name="RISK_PER_TRADE", label="Risk per trade", field_type=FieldType.FLOAT, destination=Destination.ENV, required=True, group="Env overrides"),
    ParamDef(name="BREAKOUT_LOOKBACK_PERIOD", label="Breakout lookback period", field_type=FieldType.INT, destination=Destination.ENV, required=True, group="Env overrides"),
    ParamDef(name="ZONE_INVERSION_MARGIN_ATR", label="Zone inversion margin (ATR)", field_type=FieldType.FLOAT, destination=Destination.ENV, required=True, group="Env overrides"),
    ParamDef(name="BREAKOUT_MIN_STRENGTH_ATR", label="Breakout min strength (ATR)", field_type=FieldType.FLOAT, destination=Destination.ENV, required=True, group="Env overrides"),
    ParamDef(name="MIN_RISK_DISTANCE_ATR", label="Min risk distance (ATR)", field_type=FieldType.FLOAT, destination=Destination.ENV, required=True, group="Env overrides"),
    ParamDef(name="SR_CANCELLATION_THRESHOLD_ATR", label="S/R cancellation threshold (ATR)", field_type=FieldType.FLOAT, destination=Destination.ENV, required=True, group="Env overrides"),
    ParamDef(name="SL_BUFFER_ATR", label="SL buffer (ATR)", field_type=FieldType.FLOAT, destination=Destination.ENV, required=True, group="Env overrides"),
    ParamDef(name="EMA_LENGTH", label="EMA length", field_type=FieldType.INT, destination=Destination.ENV, required=True, group="Env overrides"),
    ParamDef(name="CHECK_FOR_DAILY_RSI", label="Check daily RSI", field_type=FieldType.BOOL, destination=Destination.ENV, required=False, group="Env overrides", fallback_default=True),
    ParamDef(name="BACKTEST_FETCH_CSV_URL", label="Backtest CSV fetch server URL", field_type=FieldType.STR, destination=Destination.ENV, required=False, group="Env overrides"),
    # ----------------------------
    # Live trading (MT5)
    # ----------------------------
    ParamDef(name="MT5_LOGIN", label="MT5 Login", field_type=FieldType.INT, destination=Destination.ENV, required=False, group="Live (MT5)"),
    ParamDef(name="MT5_PASSWORD", label="MT5 Password", field_type=FieldType.STR, destination=Destination.ENV, required=False, group="Live (MT5)"),
    ParamDef(name="MT5_SERVER", label="MT5 Server", field_type=FieldType.STR, destination=Destination.ENV, required=False, group="Live (MT5)"),
    ParamDef(name="MT5_PATH", label="MT5 Terminal Path", field_type=FieldType.STR, destination=Destination.ENV, required=False, group="Live (MT5)"),
    # ----------------------------
    # Meta (hidden)
    # ----------------------------
    ParamDef(name="MODE", label="MODE", field_type=FieldType.HIDDEN, destination=Destination.META, required=False, group="Meta", fallback_default="backtest"),
    ParamDef(name="MARKET_TYPE", label="MARKET_TYPE", field_type=FieldType.HIDDEN, destination=Destination.META, required=False, group="Meta", fallback_default="forex"),
]


def get_param_definitions() -> List[Dict[str, Any]]:
    """Get parameter definitions as API-friendly format"""
    defs_payload = []
    for d in PARAM_DEFS:
        defs_payload.append({
            "name": d.name,
            "label": d.label,
            "field_type": d.field_type.value,
            "destination": d.destination.value,
            "required": d.required,
            "group": d.group,
            "help_text": d.help_text,
            "choices": d.choices or [],
        })
    return defs_payload


def get_initial_form_data() -> Dict[str, Any]:
    """Get initial form values from parameter definitions"""
    initial = {}
    for d in PARAM_DEFS:
        if d.fallback_default is not None:
            initial[d.name] = d.fallback_default
    return initial


def get_strategies() -> List[Dict[str, str]]:
    """Get available strategies"""
    return [
        {"id": "break_retest", "label": "Break + Retest"},
    ]


def get_timeframe_choices() -> List[TimeframeChoice]:
    """Get timeframe choices"""
    return [TimeframeChoice(value=value, label=label) for value, label in TIMEFRAME_CHOICES]


def defs_by_group() -> Dict[str, List[ParamDef]]:
    """Group parameter definitions by group"""
    groups: Dict[str, List[ParamDef]] = {}
    for d in PARAM_DEFS:
        groups.setdefault(d.group, []).append(d)
    return groups
