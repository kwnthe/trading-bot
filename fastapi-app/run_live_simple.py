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

# Import ChartOverlayManager for live chart overlays
try:
    # Add parent directories for src imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    
    from src.infrastructure.ChartOverlayManager import ChartOverlayManager
    from src.models.chart_markers import ChartDataType, ChartMarkerType
    CHART_OVERLAY_AVAILABLE = True
    print("ChartOverlayManager imports successful!")
except ImportError as e:
    CHART_OVERLAY_AVAILABLE = False
    print(f"Warning: ChartOverlayManager not available: {e}")
    print("Live overlays disabled")

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
        self.chart_overlay_manager = None
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
        
        # Initialize ChartOverlayManager for live session
        if CHART_OVERLAY_AVAILABLE:
            live_session_dir = self.live_data_manager.session_dir
            overlay_file_path = live_session_dir / "chart_overlays.json"
            self.chart_overlay_manager = ChartOverlayManager(str(overlay_file_path))
            print(f"ChartOverlayManager initialized: {overlay_file_path}")
        
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
                    
                    # Update chart overlays with live data
                    self.update_chart_overlays(data)
                    
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
    
    def update_chart_overlays(self, data: Dict[str, Any]):
        """Update chart overlays with live data"""
        if not CHART_OVERLAY_AVAILABLE or not self.chart_overlay_manager:
            return
        
        try:
            # Get current timestamp
            current_time = int(time.time())
            
            # Add EMA data from live data
            if 'ema' in data and data['ema']:
                for ema_point in data['ema'][-10:]:  # Last 10 EMA points
                    ema_time = int(ema_point['time'])
                    ema_value = float(ema_point['value'])
                    self.chart_overlay_manager.add_overlay_data(
                        datetime_number=ema_time,
                        data_type=ChartDataType.EMA,
                        data_feed_index=0,
                        points=[{"time": ema_time, "value": ema_value}]
                    )
            
            # Add candle data (can be used for support/resistance calculation)
            if 'candles' in data and data['candles']:
                latest_candle = data['candles'][-1]
                candle_time = int(latest_candle['time'])
                
                # Add a marker for each new candle
                self.chart_overlay_manager.add_overlay_data(
                    datetime_number=candle_time,
                    data_type=ChartDataType.MARKER,
                    data_feed_index=0,
                    marker_type=ChartMarkerType.RETEST_ORDER_PLACED,
                    price=float(latest_candle['close']),
                    direction="neutral"
                )
            
            # Save overlays to file
            self.chart_overlay_manager.save_to_file()
            
        except Exception as e:
            print(f"Error updating chart overlays: {e}")

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
    parser.add_argument('--session-dir', help='Session directory (for web app compatibility)')
    
    args = parser.parse_args()
    
    # Handle session-dir from web app
    if args.session_dir:
        # Extract session ID from directory path and load params
        session_dir = Path(args.session_dir)
        params_file = session_dir / "params.json"
        
        if params_file.exists():
            with open(params_file, 'r') as f:
                params = json.load(f)
            
            # Extract session ID from params or directory
            session_id = params.get('session_id') or session_dir.name
            symbol = params.get('symbol', 'BTCUSD')
            timeframe = params.get('timeframe', 'H1')
            login = params.get('login', 8024305)
            password = params.get('password', 'Mmw2323!')
            server = params.get('server', 'ExclusiveMarkets-Demo')
            candles = params.get('candles', 10)
        else:
            print(f"Error: params.json not found in {session_dir}")
            return
    else:
        # Command line mode
        session_id = args.session_id
        symbol = args.symbol
        timeframe = args.timeframe
        login = args.login
        password = args.password
        server = args.server
        candles = args.candles
    
    # Create and run live session
    runner = LiveRunner(session_id)
    runner.run_session(symbol, timeframe, login, password, server, candles)

if __name__ == '__main__':
    main()
