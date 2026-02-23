#!/usr/bin/env python3
"""
Live trading runner using the FastAPI LiveDataManager
Replaces the deleted web-app/backtests/runner/run_live.py
"""
import argparse
import json
import os
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

# Check for MetaTrader5 availability
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("Warning: MetaTrader5 not available, live trading disabled")

# WebSocket client for streaming chart updates
try:
    import asyncio
    import websockets
    from websockets.exceptions import ConnectionClosed, ConnectionClosedError
    WEBSOCKET_AVAILABLE = True
    print("WebSocket streaming enabled")
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("Warning: websockets library not available, WebSocket streaming disabled")

# Import LiveDataManager
from app.services.live_data_manager import LiveDataManager

# WebSocket broadcast function placeholder
def broadcast_chart_update(session_id: str, data: Dict[str, Any]):
    """Placeholder for WebSocket broadcast function"""
    if WEBSOCKET_AVAILABLE:
        # This would connect to the FastAPI WebSocket endpoint
        pass
    else:
        print("Warning: WebSocket broadcast not available, live streaming disabled")

class LiveRunner:
    """Live trading runner using FastAPI LiveDataManager"""
    
    def __init__(self, session_id: str = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.live_data_manager = None
        self.running = False
        
    def initialize_mt5(self, login: int, password: str, server: str) -> bool:
        """Initialize MetaTrader5 connection"""
        if not MT5_AVAILABLE:
            print("Error: MetaTrader5 not available")
            return False
            
        if not mt5.initialize():
            print(f"Failed to initialize MT5: {mt5.last_error()}")
            return False
            
        if not mt5.login(login, password, server):
            print(f"Failed to login to MT5: {mt5.last_error()}")
            mt5.shutdown()
            return False
            
        print(f"Successfully connected to MT5: {server}")
        return True
    
    def collect_data(self, symbol: str, timeframe: str, candle_count: int = 10) -> Dict[str, Any]:
        """Collect market data from MT5"""
        if not MT5_AVAILABLE:
            return {}
            
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            print(f"Symbol {symbol} not found")
            return {}
            
        # Get recent candles (using specified count)
        mt5_timeframe = getattr(mt5, f'TIMEFRAME_{timeframe}', mt5.TIMEFRAME_H1)
        candles = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, candle_count)
        
        if candles is None or len(candles) == 0:
            print(f"No candles data for {symbol}")
            return {}
        
        # Convert to list of dicts
        candle_data = []
        for candle in candles:
            candle_data.append({
                'time': int(candle['time']),
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close']),
                'volume': int(candle['tick_volume'])
            })
        
        # Generate some sample EMA data (using candle count)
        ema_data = []
        for i, candle in enumerate(candle_data[-candle_count:]):  # Last N candles
            ema_data.append({
                'time': int(candle['time']),
                'value': float(candle['close'])  # Simple EMA using close price
            })
        
        return {
            'candles': candle_data,
            'ema': ema_data,
            'symbol': symbol,
            'timeframe': timeframe,
            'timestamp': int(time.time())
        }
    
    def run_session(self, symbol: str, timeframe: str, login: int, password: str, server: str, candle_count: int = 10):
        """Run a live trading session"""
        print(f"Starting live session for {symbol} {timeframe}")
        
        # Initialize LiveDataManager
        self.live_data_manager = LiveDataManager(symbol, timeframe, self.session_id)
        
        # Initialize MT5
        if not self.initialize_mt5(login, password, server):
            print("Failed to initialize MT5, exiting")
            return
        
        self.running = True
        sequence = 0
        
        try:
            while self.running:
                sequence += 1
                
                # Collect data
                data = self.collect_data(symbol, timeframe, candle_count)
                
                if data:
                    # Update LiveDataManager
                    self.live_data_manager.update_from_live_runner_output(data)
                    self.live_data_manager.save()
                    
                    # Broadcast via WebSocket
                    broadcast_chart_update(self.session_id, self.live_data_manager.data)
                    
                    # Update status
                    self.update_status(sequence)
                    
                    print(f"Processed sequence {sequence}: {len(data.get('candles', []))} candles")
                else:
                    print(f"No data collected for sequence {sequence}")
                
                # Wait before next collection
                time.sleep(60)  # Collect every minute
                
        except KeyboardInterrupt:
            print("Live session stopped by user")
        except Exception as e:
            print(f"Error in live session: {e}")
            traceback.print_exc()
        finally:
            self.running = False
            if MT5_AVAILABLE and mt5.initialize():
                mt5.shutdown()
            print("Live session ended")
    
    def update_status(self, sequence: int):
        """Update session status file"""
        status_file = Path(self.live_data_manager.session_dir) / "status.json"
        status_data = {
            "state": "running",
            "sequence": sequence,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id
        }
        
        with open(status_file, 'w') as f:
            json.dump(status_data, f, indent=2)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Run live trading session')
    parser.add_argument('--symbol', default='BTCUSD', help='Trading symbol')
    parser.add_argument('--timeframe', default='H1', help='Timeframe')
    parser.add_argument('--login', type=int, default=8024305, help='MT5 login')
    parser.add_argument('--password', default='Mmw2323!', help='MT5 password')
    parser.add_argument('--server', default='ExclusiveMarkets-Demo', help='MT5 server')
    parser.add_argument('--session-id', help='Session ID (auto-generated if not provided)')
    parser.add_argument('--candles', type=int, default=10, help='Number of candles to collect (default: 10)')
    
    args = parser.parse_args()
    
    # Create and run live session
    runner = LiveRunner(args.session_id)
    runner.run_session(args.symbol, args.timeframe, args.login, args.password, args.server, args.candles)

if __name__ == '__main__':
    main()
