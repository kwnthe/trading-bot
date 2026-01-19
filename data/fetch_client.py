"""
MT5 Data Fetch Client

A client program that connects to a fetch server and downloads CSV files.

Usage:
    python fetch_client.py --server SERVER_IP:PORT [options]

Example:
    python fetch_client.py \
        --server 192.168.1.100:5000 \
        --symbol GBPAUD \
        --timeframe H1 \
        --start "2025-12-01 00:00" \
        --end "2025-12-16 23:59" \
        --output ./data.csv
"""

import argparse
import requests
import sys
from pathlib import Path

from .fetch_constants import TIMEFRAME_MAP, DEFAULT_SYMBOL, DEFAULT_START, DEFAULT_END, parse_datetime


def fetch_from_server(server_url, symbol, timeframe, start, end, output_path=None):
    """
    Fetch CSV data from the server.
    
    Args:
        server_url: Base URL of the server (e.g., "http://192.168.1.100:5000")
        symbol: Trading symbol
        timeframe: Timeframe string (e.g., "H1")
        start: Start datetime string
        end: End datetime string
        output_path: Optional path to save CSV file
    
    Returns:
        Path to saved CSV file
    """
    # Prepare request payload
    payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "start": start,
        "end": end
    }
    
    # Make request
    try:
        response = requests.post(
            f"{server_url}/fetch",
            json=payload,
            timeout=300  # 5 minute timeout for large data requests
        )
        
        # Check for errors
        if response.status_code != 200:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", "Unknown error")
                raise RuntimeError(f"Server error: {error_msg}")
            except:
                raise RuntimeError(f"Server error: HTTP {response.status_code} - {response.text}")
        
        # Determine output filename
        if output_path is None:
            # Generate filename similar to fetch.py
            start_dt = parse_datetime(start)
            end_dt = parse_datetime(end)
            filename = f"{symbol}_{timeframe}_{start_dt.date()}_{end_dt.date()}.csv"
            output_path = Path.cwd() / filename
        else:
            output_path = Path(output_path)
        
        # Save CSV file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        
        # Verify the CSV file was created and has content
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"CSV file was not created or is empty: {output_path}")
        
        # Quick validation: check if CSV has expected columns
        try:
            import pandas as pd
            test_df = pd.read_csv(output_path, nrows=1)
            if 'time' not in test_df.columns and 'datetime' not in test_df.columns and 'timestamp' not in test_df.columns:
                raise RuntimeError(f"CSV file does not contain a time/datetime column. Found columns: {list(test_df.columns)}")
        except Exception as e:
            # If validation fails, log but don't fail - let the CSV reader handle it
            import warnings
            warnings.warn(f"CSV validation warning: {e}")
        
        return output_path
        
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"Failed to connect to server at {server_url}. Is the server running?")
    except requests.exceptions.Timeout:
        raise RuntimeError(f"Request timed out. The server may be processing a large dataset.")
    except Exception as e:
        raise RuntimeError(f"Request failed: {str(e)}")


def check_server_health(server_url):
    """Check if server is reachable and healthy."""
    try:
        response = requests.get(f"{server_url}/health", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def get_server_info(server_url):
    """Get server information and available parameters."""
    try:
        response = requests.get(f"{server_url}/fetch/info", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="MT5 Data Fetch Client - Fetch CSV data from remote server"
    )
    
    parser.add_argument(
        '--server',
        required=True,
        help='Server address in format IP:PORT or HOST:PORT (e.g., 192.168.1.100:5000)'
    )
    
    parser.add_argument(
        '--symbol',
        default=DEFAULT_SYMBOL,
        help=f'Trading symbol (default: {DEFAULT_SYMBOL})'
    )
    
    parser.add_argument(
        '--timeframe',
        choices=list(TIMEFRAME_MAP.keys()),
        default='H1',
        help='Timeframe (default: H1)'
    )
    
    parser.add_argument(
        '--start',
        default=DEFAULT_START.strftime('%Y-%m-%d'),
        help=f'Start datetime in format YYYY-MM-DD or YYYY-MM-DD HH:MM (default: {DEFAULT_START.strftime("%Y-%m-%d")})'
    )
    
    parser.add_argument(
        '--end',
        default=DEFAULT_END.strftime('%Y-%m-%d'),
        help=f'End datetime in format YYYY-MM-DD or YYYY-MM-DD HH:MM (default: {DEFAULT_END.strftime("%Y-%m-%d")})'
    )
    
    parser.add_argument(
        '--output',
        '-o',
        help='Output CSV file path (default: auto-generated in current directory)'
    )
    
    parser.add_argument(
        '--check',
        action='store_true',
        help='Check server health and exit'
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='Get server info and exit'
    )
    
    args = parser.parse_args()
    
    # Parse server URL
    if '://' not in args.server:
        server_url = f"http://{args.server}"
    else:
        server_url = args.server
    
    # Remove trailing slash
    server_url = server_url.rstrip('/')
    
    # Health check mode
    if args.check:
        print(f"Checking server health at {server_url}...")
        health = check_server_health(server_url)
        if health:
            print(f"✓ Server is healthy: {health}")
            sys.exit(0)
        else:
            print(f"✗ Server is not responding")
            sys.exit(1)
    
    # Info mode
    if args.info:
        print(f"Getting server info from {server_url}...")
        info = get_server_info(server_url)
        if info:
            import json
            print(json.dumps(info, indent=2))
            sys.exit(0)
        else:
            print(f"✗ Failed to get server info")
            sys.exit(1)
    
    # Fetch mode
    print(f"Connecting to server: {server_url}")
    print(f"Parameters:")
    print(f"  Symbol: {args.symbol}")
    print(f"  Timeframe: {args.timeframe}")
    print(f"  Start: {args.start}")
    print(f"  End: {args.end}")
    
    try:
        output_path = fetch_from_server(
            server_url=server_url,
            symbol=args.symbol,
            timeframe=args.timeframe,
            start=args.start,
            end=args.end,
            output_path=args.output
        )
        
        print(f"\n✓ Successfully fetched data")
        print(f"  Saved to: {output_path}")
        print(f"  Size: {output_path.stat().st_size:,} bytes")
        
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

