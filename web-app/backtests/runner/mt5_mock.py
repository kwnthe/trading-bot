"""
Mock MetaTrader5 for testing WebSocket streaming in WSL.
This simulates MT5 data without requiring actual MT5 installation.
"""

import time
import random
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class MockSymbolInfo:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.visible = True
        self.trade_contract_size = 100000
        self.volume_min = 0.01
        self.volume_max = 100.0
        self.volume_step = 0.01
        self.point = 0.00001
        self.digits = 5
        self.spread = random.randint(1, 5)
        self.swap_long = random.uniform(-5, 5)
        self.swap_short = random.uniform(-5, 5)

class MockAccountInfo:
    def __init__(self):
        self.balance = 100000.0
        self.equity = random.uniform(95000, 105000)
        self.profit = random.uniform(-5000, 5000)
        self.margin = random.uniform(1000, 10000)
        self.margin_free = self.equity - self.margin

def symbol_info(symbol: str) -> Optional[MockSymbolInfo]:
    """Mock symbol info."""
    return MockSymbolInfo(symbol)

def symbol_select(symbol: str, enable: bool) -> bool:
    """Mock symbol selection."""
    return True

def copy_rates_from_pos(symbol: str, timeframe: int, start_pos: int, count: int) -> Optional[List[Dict]]:
    """Mock rate data generation."""
    if count <= 0:
        return None
        
    current_time = time.time()
    rates = []
    
    # Generate realistic price data
    base_price = {
        'XAGUSD': 22.5,
        'XAUUSD': 2000.0,
        'EURUSD': 1.08,
        'GBPUSD': 1.26,
        'USDJPY': 150.0
    }.get(symbol, 1.0)
    
    for i in range(count):
        timestamp = int(current_time - (count - i) * 60)  # 1-minute intervals
        
        # Generate OHLC data with small random movements
        variation = random.uniform(-0.001, 0.001)
        open_price = base_price + variation
        high_price = open_price + random.uniform(0, 0.0005)
        low_price = open_price - random.uniform(0, 00005)
        close_price = open_price + random.uniform(-0.0003, 0.0003)
        
        rates.append({
            'time': timestamp,
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'tick_volume': random.randint(50, 200),
            'spread': random.randint(1, 5),
            'real_volume': 0
        })
        
        base_price = close_price  # Use close as next open
    
    return rates

def account_info() -> MockAccountInfo:
    """Mock account info."""
    return MockAccountInfo()

def initialize() -> bool:
    """Mock MT5 initialization."""
    print("🔧 Mock MT5 initialized for testing")
    return True

def shutdown() -> bool:
    """Mock MT5 shutdown."""
    print("🔧 Mock MT5 shutdown")
    return True

# Mock constants
TIMEFRAME_M1 = 1
TIMEFRAME_M5 = 5
TIMEFRAME_M15 = 15
TIMEFRAME_M30 = 30
TIMEFRAME_H1 = 60
TIMEFRAME_H4 = 240
TIMEFRAME_D1 = 1440

print("🧪 Mock MetaTrader5 loaded - WebSocket testing enabled")
