"""
MT5 Data Fetch Server

A Flask server that accepts requests to fetch MT5 historical data
and returns CSV files.

Usage:
    python fetch_server.py [--host HOST] [--port PORT]

Example:
    python fetch_server.py --host 0.0.0.0 --port 5000
"""

from flask import Flask, request, jsonify, send_file
from datetime import datetime
import argparse
from pathlib import Path
import traceback

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from data.fetch import fetch_candles, TIMEFRAME_MAP
from data.fetch_constants import parse_datetime, DEFAULT_SYMBOL, DEFAULT_START, DEFAULT_END

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "service": "mt5-fetch-server"})


@app.route('/fetch', methods=['POST'])
def fetch():
    """
    Fetch MT5 historical data and return CSV file.
    
    Expected JSON payload:
    {
        "symbol": "EURUSD",           # Optional, default: "EURUSD"
        "timeframe": "H1",            # Optional, default: "H1"
        "start": "2025-12-01 00:00",  # Optional, default: "2025-12-01"
        "end": "2025-12-16 23:59"     # Optional, default: "2025-12-16"
    }
    
    Returns:
        CSV file with appropriate headers
    """
    try:
        # Get parameters from JSON body
        data = request.get_json() or {}
        
        # Parse parameters with defaults
        symbol = data.get('symbol', DEFAULT_SYMBOL)
        timeframe_str = data.get('timeframe', 'H1')
        start_str = data.get('start', DEFAULT_START.strftime('%Y-%m-%d'))
        end_str = data.get('end', DEFAULT_END.strftime('%Y-%m-%d'))
        
        # Validate timeframe
        if timeframe_str not in TIMEFRAME_MAP:
            return jsonify({
                "error": f"Invalid timeframe. Must be one of: {list(TIMEFRAME_MAP.keys())}"
            }), 400
        
        timeframe = TIMEFRAME_MAP[timeframe_str]
        
        # Parse dates
        try:
            start = parse_datetime(start_str)
        except Exception as e:
            return jsonify({
                "error": f"Invalid start date format: {start_str}. Use YYYY-MM-DD or YYYY-MM-DD HH:MM"
            }), 400
        
        try:
            end = parse_datetime(end_str)
        except Exception as e:
            return jsonify({
                "error": f"Invalid end date format: {end_str}. Use YYYY-MM-DD or YYYY-MM-DD HH:MM"
            }), 400
        
        # Fetch candles
        result = fetch_candles(
            mode="csv",
            start=start,
            end=end,
            symbol=symbol,
            timeframe=timeframe
        )
        
        if not result.get("success"):
            return jsonify({
                "error": "Failed to fetch candles",
                "details": result
            }), 500
        
        # Send CSV file
        csv_path = Path(result["path"])
        return send_file(
            csv_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=csv_path.name
        )
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }), 500


@app.route('/fetch/info', methods=['GET'])
def fetch_info():
    """Get information about available parameters."""
    return jsonify({
        "available_timeframes": list(TIMEFRAME_MAP.keys()),
        "default_symbol": DEFAULT_SYMBOL,
        "default_timeframe": "H1",
        "date_format": "YYYY-MM-DD or YYYY-MM-DD HH:MM",
        "example_request": {
            "symbol": "EURUSD",
            "timeframe": "H1",
            "start": "2025-12-01 00:00",
            "end": "2025-12-16 23:59"
        }
    })


def main():
    parser = argparse.ArgumentParser(
        description="MT5 Data Fetch Server"
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port to bind to (default: 5000)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    
    args = parser.parse_args()
    
    print(f"Starting MT5 Fetch Server on {args.host}:{args.port}")
    print(f"Health check: http://{args.host}:{args.port}/health")
    print(f"API info: http://{args.host}:{args.port}/fetch/info")
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()

