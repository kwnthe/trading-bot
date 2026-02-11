from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from .params import PARAM_DEFS, ParamDef


TEST_PY_DEFAULTS = {
    # Backtesting() call params (test.py)
    "symbols": "XAGUSD",
    "timeframe": "H1",
    # Note: datetime-local inputs are naive; we treat them as UTC in the runner.
    "start_date": datetime(2026, 1, 1, 0, 0, 0),
    "end_date": datetime(2026, 2, 1, 0, 0, 0),  # "now" at request time
    "max_candles": "",
    # Env overrides explicitly set in test.py
    "ZONE_INVERSION_MARGIN_ATR": "1",
    "BREAKOUT_MIN_STRENGTH_ATR": "0.2",
    "MIN_RISK_DISTANCE_ATR": "0.5",
    "RR": "2",
    "CHECK_FOR_DAILY_RSI": "True",
    "EMA_LENGTH": "40",
    "SR_CANCELLATION_THRESHOLD_ATR": "0.2",
    "SL_BUFFER_ATR": "0.3",
    "RISK_PER_TRADE": "0.01",
}


def repo_root() -> Path:
    # web-app/backtests/defaults.py -> backtests -> web-app -> repo root
    return Path(__file__).resolve().parents[2]


def load_env_defaults() -> dict[str, str]:
    env_path = repo_root() / ".env"
    values = dotenv_values(env_path)
    # dotenv_values returns Optional[str] values
    return {k: (v if v is not None else "") for k, v in values.items()}


def build_initial_form_data() -> dict[str, Any]:
    env = load_env_defaults()

    initial: dict[str, Any] = {}

    def _truthy(v: Any) -> bool:
        raw = str(v).strip().lower()
        return raw in {"1", "true", "yes", "y", "on"}

    for d in PARAM_DEFS:
        # Special-case datetimes that aren't in .env
        if d.name == "start_date":
            initial[d.name] = TEST_PY_DEFAULTS.get("start_date") or d.fallback_default or datetime.now()
            continue
        if d.name == "end_date":
            initial[d.name] = datetime.now()
            continue

        if d.name in TEST_PY_DEFAULTS:
            v = TEST_PY_DEFAULTS[d.name]
        elif d.name in env:
            v = env.get(d.name, "")
        elif d.fallback_default is not None:
            v = d.fallback_default
        else:
            v = ""

        # Normalize booleans for Django initial values
        if d.field_type == "bool":
            v = v if isinstance(v, bool) else _truthy(v)

        initial[d.name] = v

    return initial

