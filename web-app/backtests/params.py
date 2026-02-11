from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional


FieldType = Literal["str", "int", "float", "bool", "datetime", "choice", "hidden"]
Destination = Literal["backtest", "env", "meta"]


@dataclass(frozen=True)
class ParamDef:
    name: str
    label: str
    field_type: FieldType
    destination: Destination
    required: bool = True
    group: str = "General"
    help_text: str = ""
    choices: Optional[list[tuple[str, str]]] = None

    # Default resolution (in order):
    # - test_py_overrides[name] if present
    # - env_defaults[name] if present
    # - fallback_default if not None
    fallback_default: Any = None


TIMEFRAME_CHOICES: list[tuple[str, str]] = [
    ("M1", "M1"),
    ("M5", "M5"),
    ("M15", "M15"),
    ("M30", "M30"),
    ("H1", "H1"),
    ("H4", "H4"),
    ("D1", "D1"),
]


PARAM_DEFS: list[ParamDef] = [
    # ----------------------------
    # Backtesting() call parameters
    # ----------------------------
    ParamDef(
        name="symbols",
        label="Symbols (comma-separated)",
        field_type="str",
        destination="backtest",
        required=True,
        group="Backtest",
        help_text="Example: XAGUSD,XAUUSD,EURUSD",
        fallback_default="XAGUSD",
    ),
    ParamDef(
        name="timeframe",
        label="Timeframe",
        field_type="choice",
        destination="backtest",
        required=True,
        group="Backtest",
        choices=TIMEFRAME_CHOICES,
        fallback_default="H1",
    ),
    ParamDef(
        name="start_date",
        label="Start date",
        field_type="datetime",
        destination="backtest",
        required=True,
        group="Backtest",
    ),
    ParamDef(
        name="end_date",
        label="End date",
        field_type="datetime",
        destination="backtest",
        required=True,
        group="Backtest",
    ),
    ParamDef(
        name="max_candles",
        label="Max candles",
        field_type="int",
        destination="backtest",
        required=False,
        group="Backtest",
    ),
    ParamDef(
        name="spread_pips",
        label="Spread (pips)",
        field_type="float",
        destination="backtest",
        required=False,
        group="Backtest",
        fallback_default=0.0,
    ),
    # ----------------------------
    # Env overrides (strategy tuning)
    # ----------------------------
    ParamDef(name="RR", label="RR", field_type="float", destination="env", required=True, group="Env overrides"),
    ParamDef(name="INITIAL_EQUITY", label="Initial equity", field_type="float", destination="env", required=True, group="Env overrides"),
    ParamDef(name="RISK_PER_TRADE", label="Risk per trade", field_type="float", destination="env", required=True, group="Env overrides"),
    ParamDef(name="BREAKOUT_LOOKBACK_PERIOD", label="Breakout lookback period", field_type="int", destination="env", required=True, group="Env overrides"),
    ParamDef(name="ZONE_INVERSION_MARGIN_ATR", label="Zone inversion margin (ATR)", field_type="float", destination="env", required=True, group="Env overrides"),
    ParamDef(name="BREAKOUT_MIN_STRENGTH_ATR", label="Breakout min strength (ATR)", field_type="float", destination="env", required=True, group="Env overrides"),
    ParamDef(name="MIN_RISK_DISTANCE_ATR", label="Min risk distance (ATR)", field_type="float", destination="env", required=True, group="Env overrides"),
    ParamDef(name="SR_CANCELLATION_THRESHOLD_ATR", label="S/R cancellation threshold (ATR)", field_type="float", destination="env", required=True, group="Env overrides"),
    ParamDef(name="SL_BUFFER_ATR", label="SL buffer (ATR)", field_type="float", destination="env", required=True, group="Env overrides"),
    ParamDef(name="EMA_LENGTH", label="EMA length", field_type="int", destination="env", required=True, group="Env overrides"),
    ParamDef(name="CHECK_FOR_DAILY_RSI", label="Check daily RSI", field_type="bool", destination="env", required=False, group="Env overrides", fallback_default=True),
    ParamDef(name="BACKTEST_FETCH_CSV_URL", label="Backtest CSV fetch server URL", field_type="str", destination="env", required=False, group="Env overrides"),
    # ----------------------------
    # Live trading (MT5)
    # ----------------------------
    ParamDef(name="MT5_LOGIN", label="MT5 Login", field_type="int", destination="env", required=False, group="Live (MT5)"),
    ParamDef(name="MT5_PASSWORD", label="MT5 Password", field_type="str", destination="env", required=False, group="Live (MT5)"),
    ParamDef(name="MT5_SERVER", label="MT5 Server", field_type="str", destination="env", required=False, group="Live (MT5)"),
    ParamDef(name="MT5_PATH", label="MT5 Terminal Path", field_type="str", destination="env", required=False, group="Live (MT5)"),
    # ----------------------------
    # Meta (hidden)
    # ----------------------------
    ParamDef(name="MODE", label="MODE", field_type="hidden", destination="meta", required=False, group="Meta", fallback_default="backtest"),
    ParamDef(name="MARKET_TYPE", label="MARKET_TYPE", field_type="hidden", destination="meta", required=False, group="Meta", fallback_default="forex"),
]


def defs_by_group() -> dict[str, list[ParamDef]]:
    groups: dict[str, list[ParamDef]] = {}
    for d in PARAM_DEFS:
        groups.setdefault(d.group, []).append(d)
    return groups

