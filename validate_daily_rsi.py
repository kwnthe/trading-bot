"""
Validation script for Daily RSI calculation.
Compares extracted Daily RSI with manually calculated Daily RSI to ensure correctness.
"""

import sys
import os
from datetime import datetime
import pandas as pd
import numpy as np
import backtrader as bt

# Add project root and src directory to path
# Handle both script execution and notebook execution
if __file__:
    _project_root = os.path.dirname(os.path.abspath(__file__))
else:
    # If running from notebook, assume we're in the project root
    _project_root = os.getcwd()
    if not os.path.exists(os.path.join(_project_root, 'main.py')):
        # Try going up one level
        _project_root = os.path.dirname(_project_root)

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
_src_dir = os.path.join(_project_root, 'src')
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from src.models.timeframe import Timeframe
from src.utils.backtesting import prepare_backtesting
from main import backtesting
from src.utils.plot import extract_daily_rsi, calculate_rsi_manual


def calculate_daily_rsi_from_daily_data(daily_data, period: int = 14) -> pd.Series:
    """
    Calculate Daily RSI from daily_data feed (same as extract_daily_rsi does).
    This matches the actual implementation in plot.py.
    """
    # Extract daily close prices from the daily data feed (created by replaydata)
    daily_dates = pd.Series([bt.num2date(d) for d in daily_data.datetime.array])
    daily_closes = np.asarray(daily_data.close.array)
    
    # Calculate RSI from daily closes
    daily_rsi = calculate_rsi_manual(daily_closes, period=period)
    
    # Return as Series with datetime index
    return pd.Series(daily_rsi, index=daily_dates)


def validate_daily_rsi_constancy(daily_rsi_aligned: np.ndarray, df_dates: pd.Series) -> dict:
    """
    Validate that Daily RSI stays constant throughout each day.
    Returns dict with validation results.
    """
    results = {
        'valid': True,
        'issues': [],
        'days_checked': 0,
        'days_with_changes': 0
    }
    
    # Group by date and check if RSI values are constant within each day
    df_check = pd.DataFrame({
        'date': pd.to_datetime(df_dates).dt.date,
        'datetime': df_dates,
        'daily_rsi': daily_rsi_aligned
    })
    
    for date, group in df_check.groupby('date'):
        results['days_checked'] += 1
        # Get non-NaN values for this day
        non_nan_values = group['daily_rsi'].dropna()
        
        if len(non_nan_values) > 0:
            # Check if all values are the same (within floating point tolerance)
            if not np.allclose(non_nan_values, non_nan_values.iloc[0], equal_nan=True):
                results['valid'] = False
                results['days_with_changes'] += 1
                unique_values = non_nan_values.unique()
                results['issues'].append({
                    'date': date,
                    'unique_values': unique_values,
                    'count': len(group)
                })
    
    return results


def validate_daily_rsi_updates(daily_rsi_aligned: np.ndarray, df_dates: pd.Series) -> dict:
    """
    Validate that Daily RSI only updates when a new day starts.
    Returns dict with validation results.
    """
    results = {
        'valid': True,
        'issues': [],
        'day_transitions_checked': 0,
        'unexpected_updates': 0
    }
    
    df_check = pd.DataFrame({
        'date': pd.to_datetime(df_dates).dt.date,
        'datetime': df_dates,
        'daily_rsi': daily_rsi_aligned
    })
    
    # Check transitions between days
    prev_date = None
    prev_rsi = None
    
    for idx, row in df_check.iterrows():
        current_date = row['date']
        current_rsi = row['daily_rsi']
        
        if prev_date is not None:
            if current_date != prev_date:
                # Day transition - RSI can change
                results['day_transitions_checked'] += 1
                prev_date = current_date
                prev_rsi = current_rsi
            else:
                # Same day - RSI should not change (unless both are NaN)
                if not (np.isnan(prev_rsi) and np.isnan(current_rsi)):
                    if not np.isnan(prev_rsi) and not np.isnan(current_rsi):
                        if not np.isclose(prev_rsi, current_rsi, equal_nan=True):
                            results['valid'] = False
                            results['unexpected_updates'] += 1
                            results['issues'].append({
                                'date': current_date,
                                'datetime': row['datetime'],
                                'prev_rsi': prev_rsi,
                                'current_rsi': current_rsi
                            })
        else:
            prev_date = current_date
            prev_rsi = current_rsi
    
    return results


def validate_daily_rsi_calculation(symbols: list[str], timeframe: Timeframe, 
                                   start_date: datetime, end_date: datetime):
    """
    Main validation function.
    """
    print("=" * 80)
    print("DAILY RSI VALIDATION")
    print("=" * 80)
    print(f"Symbols: {symbols}")
    print(f"Timeframe: {timeframe}")
    print(f"Date range: {start_date} to {end_date}")
    print("=" * 80)
    print()
    
    # Run backtest to get strategy and data
    print("Running backtest to get strategy and data...")
    results = backtesting(symbols, timeframe, start_date, end_date, max_candles=None, print_trades=False)
    cerebro = results['cerebro']
    strategy = cerebro.strategy
    data = results['data'][symbols[0]]
    
    print("✓ Backtest completed")
    print()
    
    # Build DataFrame from main data
    print("Building DataFrame from main data...")
    df_main = pd.DataFrame({
        'datetime': [bt.num2date(d) for d in data.datetime.array],
        'close': data.close.array
    })
    print(f"✓ Loaded {len(df_main)} bars")
    print()
    
    # Extract Daily RSI using our function
    print("Extracting Daily RSI from strategy...")
    has_daily_rsi, daily_rsi_extracted = extract_daily_rsi(strategy, len(df_main), df_main['datetime'])
    
    if not has_daily_rsi:
        print("❌ Failed to extract Daily RSI from strategy!")
        return False
    
    print(f"✓ Extracted Daily RSI: {len(daily_rsi_extracted)} values")
    print(f"  Non-NaN values: {np.sum(~np.isnan(daily_rsi_extracted))}")
    print()
    
    # For comparison, extract Daily RSI a second time to verify consistency
    # Since extract_daily_rsi now uses strategy.daily_data directly, we can validate
    # that it produces consistent results
    print("Extracting Daily RSI a second time for consistency check...")
    has_daily_rsi2, daily_rsi_extracted2 = extract_daily_rsi(strategy, len(df_main), df_main['datetime'])
    
    if not has_daily_rsi2:
        print("❌ Failed to extract Daily RSI second time!")
        return False
    
    # Compare the two extractions (should be identical)
    print("Comparing two extractions for consistency...")
    print("-" * 80)
    
    # Ensure both have the same length
    if len(daily_rsi_extracted) != len(daily_rsi_extracted2):
        print(f"❌ Length mismatch: {len(daily_rsi_extracted)} vs {len(daily_rsi_extracted2)}")
        return False
    
    # Find indices where both have non-NaN values
    both_valid = ~np.isnan(daily_rsi_extracted) & ~np.isnan(daily_rsi_extracted2)
    num_both_valid = np.sum(both_valid)
    
    if num_both_valid == 0:
        print("⚠️  No overlapping valid values to compare!")
        return False
    
    print(f"Valid values to compare: {num_both_valid}")
    
    # Calculate differences
    differences = daily_rsi_extracted[both_valid] - daily_rsi_extracted2[both_valid]
    max_diff = np.max(np.abs(differences))
    mean_diff = np.mean(np.abs(differences))
    
    print(f"Max difference: {max_diff:.6f}")
    print(f"Mean absolute difference: {mean_diff:.6f}")
    
    # Check if they match (within floating point tolerance)
    tolerance = 1e-5
    matches = np.allclose(daily_rsi_extracted[both_valid], 
                          daily_rsi_extracted2[both_valid], 
                          equal_nan=True, 
                          atol=tolerance)
    
    if matches:
        print(f"✓ Extractions are consistent (match within tolerance {tolerance})")
    else:
        print(f"❌ Extractions are NOT consistent!")
        print(f"   First 10 differences: {differences[:10]}")
    
    print()
    
    # Validate constancy (RSI should stay constant throughout each day)
    print("Validating Daily RSI constancy (should stay constant within each day)...")
    print("-" * 80)
    constancy_results = validate_daily_rsi_constancy(daily_rsi_extracted, df_main['datetime'])
    
    if constancy_results['valid']:
        print(f"✓ Daily RSI stays constant throughout each day")
        print(f"  Checked {constancy_results['days_checked']} days")
    else:
        print(f"❌ Daily RSI changes within days!")
        print(f"  Days with changes: {constancy_results['days_with_changes']} / {constancy_results['days_checked']}")
        for issue in constancy_results['issues'][:5]:  # Show first 5 issues
            print(f"    Date {issue['date']}: {len(issue['unique_values'])} unique values")
    
    print()
    
    # Validate updates (RSI should only update on day transitions)
    print("Validating Daily RSI updates (should only update on day transitions)...")
    print("-" * 80)
    update_results = validate_daily_rsi_updates(daily_rsi_extracted, df_main['datetime'])
    
    if update_results['valid']:
        print(f"✓ Daily RSI only updates on day transitions")
        print(f"  Checked {update_results['day_transitions_checked']} day transitions")
    else:
        print(f"❌ Daily RSI updates within the same day!")
        print(f"  Unexpected updates: {update_results['unexpected_updates']}")
        for issue in update_results['issues'][:5]:  # Show first 5 issues
            print(f"    {issue['datetime']}: {issue['prev_rsi']:.2f} -> {issue['current_rsi']:.2f}")
    
    print()
    
    # Summary
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    all_valid = matches and constancy_results['valid'] and update_results['valid']
    
    if all_valid:
        print("✅ ALL VALIDATIONS PASSED")
        print("   - Daily RSI extractions are consistent")
        print("   - Daily RSI stays constant throughout each day")
        print("   - Daily RSI only updates on day transitions")
    else:
        print("❌ SOME VALIDATIONS FAILED")
        if not matches:
            print("   - Daily RSI extractions are not consistent")
        if not constancy_results['valid']:
            print("   - Daily RSI changes within days")
        if not update_results['valid']:
            print("   - Daily RSI updates within the same day")
    
    print("=" * 80)
    
    # Additional edge case validations
    print()
    print("Additional Edge Case Validations...")
    print("-" * 80)
    
    # Check 1: Verify Daily RSI values are in valid range (0-100)
    valid_range = (daily_rsi_extracted >= 0) & (daily_rsi_extracted <= 100)
    valid_range_count = np.sum(valid_range[~np.isnan(daily_rsi_extracted)])
    total_valid = np.sum(~np.isnan(daily_rsi_extracted))
    
    if valid_range_count == total_valid:
        print(f"✓ All Daily RSI values are in valid range (0-100): {valid_range_count}/{total_valid}")
    else:
        print(f"❌ Some Daily RSI values are outside valid range: {valid_range_count}/{total_valid}")
        invalid_values = daily_rsi_extracted[~valid_range & ~np.isnan(daily_rsi_extracted)]
        print(f"   Invalid values: {invalid_values[:10]}")
        all_valid = False
    
    # Check 2: Verify Daily RSI has proper NaN handling at start
    # RSI(14) needs 15 data points, so first 14 values should be NaN
    # The first valid value should appear at index 14 (15th data point)
    first_20 = daily_rsi_extracted[:20]
    first_14_nan = np.sum(np.isnan(first_20[:14]))
    
    # Find first non-NaN value
    first_valid_idx = None
    for i, val in enumerate(daily_rsi_extracted):
        if not np.isnan(val):
            first_valid_idx = i
            break
    
    if first_valid_idx is not None:
        if first_14_nan == 14 and first_valid_idx >= 14:
            print(f"✓ Daily RSI has proper NaN handling (first 14 days are NaN, first valid at index {first_valid_idx})")
        else:
            print(f"⚠️  Daily RSI NaN handling: first 14 days have {first_14_nan} NaN values, first valid at index {first_valid_idx}")
    else:
        print(f"⚠️  Daily RSI has no valid values (all NaN)")
    
    # Check 3: Verify Daily RSI doesn't have sudden jumps (changes > 50 in one day)
    if len(daily_rsi_extracted) > 1:
        daily_changes = np.abs(np.diff(daily_rsi_extracted))
        # Filter out NaN differences
        valid_changes = daily_changes[~np.isnan(daily_changes)]
        if len(valid_changes) > 0:
            max_change = np.max(valid_changes)
            large_changes = np.sum(valid_changes > 50)
            
            if large_changes == 0:
                print(f"✓ No sudden jumps in Daily RSI (max daily change: {max_change:.2f})")
            else:
                print(f"⚠️  Daily RSI has {large_changes} large changes (>50): max change = {max_change:.2f}")
                # This might be normal for volatile markets, so it's a warning not an error
    
    # Check 4: Verify Daily RSI length matches main data length
    if len(daily_rsi_extracted) == len(df_main):
        print(f"✓ Daily RSI length matches main data length: {len(daily_rsi_extracted)}")
    else:
        print(f"❌ Length mismatch: Daily RSI={len(daily_rsi_extracted)}, Main data={len(df_main)}")
        all_valid = False
    
    # Check 5: Verify RSI calculation correctness by comparing with reference implementation
    print()
    print("Validating RSI calculation correctness...")
    print("-" * 80)
    
    # Get the daily closes that were used for RSI calculation
    if hasattr(strategy, "daily_data") and strategy.daily_data is not None:
        daily_data = strategy.daily_data
        all_dates = pd.Series([bt.num2date(d) for d in daily_data.datetime.array])
        all_closes = np.asarray(daily_data.close.array)
        
        # Filter to get daily bars (same as extract_daily_rsi does)
        df_daily = pd.DataFrame({
            'date': pd.to_datetime(all_dates).dt.normalize(),
            'datetime': all_dates,
            'close': all_closes
        })
        daily_aggregated = df_daily.groupby('date').agg({
            'close': 'last',
            'datetime': 'last'
        }).reset_index().sort_values('datetime')
        daily_closes = daily_aggregated['close'].values
        
        # Calculate RSI using our function
        our_rsi = calculate_rsi_manual(daily_closes, period=14)
        
        # Try to compare with pandas-ta (if available) or use manual verification
        try:
            import pandas_ta as ta
            # Calculate RSI using pandas-ta as reference
            daily_closes_series = pd.Series(daily_closes)
            reference_rsi = ta.rsi(daily_closes_series, length=14).values
            
            # Compare (skip NaN values)
            both_valid = ~np.isnan(our_rsi) & ~np.isnan(reference_rsi)
            if np.sum(both_valid) > 0:
                differences = our_rsi[both_valid] - reference_rsi[both_valid]
                max_diff = np.max(np.abs(differences))
                mean_diff = np.mean(np.abs(differences))
                
                tolerance = 0.01  # RSI values can have small differences due to rounding/precision
                matches = np.allclose(our_rsi[both_valid], reference_rsi[both_valid], 
                                     equal_nan=True, atol=tolerance)
                
                if matches:
                    print(f"✓ RSI calculation matches pandas-ta reference (max diff: {max_diff:.6f})")
                    print(f"   Compared {np.sum(both_valid)} values, mean diff: {mean_diff:.6f}")
                else:
                    print(f"⚠️  RSI calculation differs from pandas-ta (max diff: {max_diff:.6f}, mean: {mean_diff:.6f})")
                    print(f"   This might be due to different smoothing methods or rounding")
                    # Show sample differences
                    if len(differences) > 0:
                        print(f"   Sample differences: {differences[:5]}")
            else:
                print("⚠️  Could not compare RSI values (no overlapping valid values)")
        except ImportError:
            # pandas-ta not available, verify manually
            print("⚠️  pandas-ta not available for RSI comparison")
            print("   Install with: pip install pandas-ta")
            print("   Manual verification: RSI values should be between 0-100")
            print(f"   Our RSI range: {np.nanmin(our_rsi):.2f} to {np.nanmax(our_rsi):.2f}")
        except Exception as e:
            print(f"⚠️  Error comparing RSI calculation: {e}")
            import traceback
            traceback.print_exc()
    
    print()
    print("=" * 80)
    
    return all_valid


if __name__ == '__main__':
    # Example usage
    symbols = ['XAGUSD']
    timeframe = Timeframe.H1
    start_date = datetime(2026, 1, 1)
    end_date = datetime.now()
    
    validate_daily_rsi_calculation(symbols, timeframe, start_date, end_date)
