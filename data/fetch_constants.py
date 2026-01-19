"""
Fetch Constants and Utilities

Non-MetaTrader5 dependencies for fetch operations.
This module can be safely imported on any platform (including Mac).
"""

import argparse
from datetime import datetime
from pathlib import Path

# ============================================================================
# DEFAULT CONFIGURATION
# ============================================================================
DEFAULT_SYMBOL = "EURUSD"
DEFAULT_MODE = "csv"
DEFAULT_START = datetime(2025, 12, 1)
DEFAULT_END = datetime(2025, 12, 16)

# ============================================================================
# SCRIPT DIRECTORY
# ============================================================================
SCRIPT_DIR = Path(__file__).resolve().parent

# ============================================================================
# TIMEFRAME MAP (string-based, no MT5 dependencies)
# ============================================================================
TIMEFRAME_MAP = {
    "M1": "M1",
    "M5": "M5",
    "M15": "M15",
    "M30": "M30",
    "H1": "H1",
    "H4": "H4",
    "D1": "D1",
    "W1": "W1",
    "MN1": "MN1",
}

# Default timeframe string (used when MT5 constants aren't available)
DEFAULT_TIMEFRAME = "H1"

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def generate_csv_filename(symbol: str, timeframe: str, start_date: datetime, end_date: datetime):
    """Generate CSV filename from symbol, timeframe, and date range."""
    return f"{symbol}_{timeframe}_{start_date.date()}_{end_date.date()}.csv"


def parse_datetime(value):
    """Parse datetime string in format YYYY-MM-DD or YYYY-MM-DD HH:MM."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(
        "Date must be YYYY-MM-DD or YYYY-MM-DD HH:MM"
    )
