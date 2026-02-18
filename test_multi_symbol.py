#!/usr/bin/env python3
"""
Test script to verify multi-symbol chart overlay support
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.infrastructure.ChartOverlayManager import ChartOverlayManager
from src.models.chart_markers import ChartDataType, ChartMarkerType

def test_multi_symbol_support():
    """Test that multiple symbols can store data without overwriting each other"""
    
    # Create a temporary directory for testing
    test_dir = Path("/tmp/test_multi_symbol")
    test_dir.mkdir(exist_ok=True)
    
    # Create ChartOverlayManager for test directory
    manager = ChartOverlayManager.for_job_directory(test_dir)
    
    # Test data
    timestamp = 1759413600  # Same timestamp for both symbols
    
    # Add data for symbol 0 (XAGUSD)
    manager.add_overlay_data(
        datetime_number=timestamp,
        data_type=ChartDataType.EMA,
        data_feed_index=0,
        points=[{'time': timestamp, 'value': 47.2161}]
    )
    
    manager.add_overlay_data(
        datetime_number=timestamp,
        data_type=ChartDataType.SUPPORT,
        data_feed_index=0,
        points=[{'time': timestamp, 'value': 47.21499}]
    )
    
    manager.add_overlay_data(
        datetime_number=timestamp,
        data_type=ChartDataType.MARKER,
        data_feed_index=0,
        price=47.25,
        marker_type=ChartMarkerType.RETEST_ORDER_PLACED
    )
    
    # Add data for symbol 1 (XAUUSD) - same timestamp
    manager.add_overlay_data(
        datetime_number=timestamp,
        data_type=ChartDataType.EMA,
        data_feed_index=1,
        points=[{'time': timestamp, 'value': 2085.42}]
    )
    
    manager.add_overlay_data(
        datetime_number=timestamp,
        data_type=ChartDataType.SUPPORT,
        data_feed_index=1,
        points=[{'time': timestamp, 'value': 2080.15}]
    )
    
    manager.add_overlay_data(
        datetime_number=timestamp,
        data_type=ChartDataType.MARKER,
        data_feed_index=1,
        price=2086.50,
        marker_type=ChartMarkerType.RETEST_ORDER_PLACED
    )
    
    # Save to file
    manager.save_to_file()
    
    # Read and verify the JSON structure
    json_file = test_dir / "chart_overlays.json"
    if json_file.exists():
        with open(json_file, 'r') as f:
            import json
            data = json.load(f)
            
        print("✅ Multi-symbol JSON structure:")
        print(json.dumps(data, indent=2))
        
        # Verify both symbols have data (JSON keys are strings)
        timestamp_str = str(timestamp)
        if timestamp_str in data:
            symbol_data = data[timestamp_str]
            if '0' in symbol_data and '1' in symbol_data:
                print("\n✅ SUCCESS: Both symbols have separate data entries!")
                print(f"Symbol 0 EMA: {symbol_data['0'].get('ema')}")
                print(f"Symbol 1 EMA: {symbol_data['1'].get('ema')}")
                
                # Test legacy format conversion
                legacy_data = manager.convert_to_legacy_format()
                print(f"\n✅ Legacy format has {len(legacy_data['ema'])} EMA entries")
                print(f"✅ Legacy format has {len(legacy_data['markers'])} marker entries")
                
                # Verify symbol indices are preserved
                ema_symbols = [ema['symbol'] for ema in legacy_data['ema']]
                marker_symbols = [marker['symbol'] for marker in legacy_data['markers']]
                
                print(f"EMA symbols: {ema_symbols}")
                print(f"Marker symbols: {marker_symbols}")
                
                if 0 in ema_symbols and 1 in ema_symbols:
                    print("✅ Symbol indices correctly preserved in legacy format!")
                else:
                    print("❌ Symbol indices not preserved correctly")
                    
                return True
            else:
                print("❌ FAILED: Missing symbol data")
                return False
        else:
            print("❌ FAILED: No timestamp entry")
            return False
    else:
        print("❌ FAILED: JSON file not created")
        return False

if __name__ == "__main__":
    success = test_multi_symbol_support()
    if success:
        print("\n🎉 Multi-symbol support test PASSED!")
    else:
        print("\n❌ Multi-symbol support test FAILED!")
        sys.exit(1)
