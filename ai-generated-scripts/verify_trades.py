"""
Script to verify trade data and calculations
Run this after a backtest to validate trade records
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.models.order import OrderSide

def verify_trade(trade, trade_num, verbose=False):
    """Verify a single trade's data and calculations."""
    if verbose:
        print(f"\n{'='*80}")
        print(f"TRADE #{trade_num} VERIFICATION")
        print(f"{'='*80}")
    
    trade_id = trade.get('trade_id', 'N/A')[:8]
    symbol = trade.get('symbol', 'N/A')
    side = trade.get('order_side')
    side_name = side.name if isinstance(side, OrderSide) else str(side)
    
    if verbose:
        print(f"Trade ID: {trade_id}")
        print(f"Symbol: {symbol}")
        print(f"Side: {side_name}")
        print(f"State: {trade.get('state')}")
    
    # Entry prices
    entry_order_price = trade.get('entry_price')
    entry_executed_price = trade.get('entry_executed_price')
    entry_price_used = entry_executed_price or entry_order_price
    
    if verbose:
        print(f"\nEntry Prices:")
        print(f"  Order Price: {entry_order_price}")
        print(f"  Executed Price: {entry_executed_price}")
        print(f"  Price Used for PnL: {entry_price_used}")
    
    # Exit prices
    exit_price = trade.get('exit_price')
    tp_price = trade.get('tp')
    sl_price = trade.get('sl')
    
    if verbose:
        print(f"\nExit Prices:")
        print(f"  Exit Price: {exit_price}")
        print(f"  TP Price: {tp_price}")
        print(f"  SL Price: {sl_price}")
    
    # Size
    size = abs(trade.get('size', 0))
    if verbose:
        print(f"\nPosition Size: {size}")
    
    # PnL calculation
    pnl = trade.get('pnl')
    close_reason = trade.get('close_reason')
    
    # Calculate expected PnL
    if exit_price and entry_price_used:
        if side == OrderSide.BUY:
            expected_pnl = (exit_price - entry_price_used) * size
        else:  # SELL
            expected_pnl = (entry_price_used - exit_price) * size
    else:
        expected_pnl = None
    
    if verbose:
        print(f"\nPnL:")
        print(f"  Recorded PnL: {pnl}")
        if expected_pnl is not None:
            print(f"  Calculated PnL: {expected_pnl}")
            print(f"  Difference: {abs(pnl - expected_pnl) if pnl is not None else 'N/A'}")
            if pnl is not None and abs(pnl - expected_pnl) > 0.01:
                print(f"  ⚠️  WARNING: PnL mismatch!")
    
    # Verify exit price matches TP/SL
    if verbose:
        print(f"\nExit Price Verification:")
    if close_reason == 'TP' and tp_price:
        diff = abs(exit_price - tp_price) if exit_price else None
        if verbose:
            print(f"  Close Reason: TP")
            print(f"  Exit Price: {exit_price}")
            print(f"  TP Price: {tp_price}")
            print(f"  Difference: {diff}")
            if diff and diff > 0.0001:  # Allow small difference for slippage
                print(f"  ⚠️  WARNING: Exit price doesn't match TP (may be due to slippage)")
    elif close_reason == 'SL' and sl_price:
        diff = abs(exit_price - sl_price) if exit_price else None
        if verbose:
            print(f"  Close Reason: SL")
            print(f"  Exit Price: {exit_price}")
            print(f"  SL Price: {sl_price}")
            print(f"  Difference: {diff}")
            if diff and diff > 0.0001:  # Allow small difference for slippage
                print(f"  ⚠️  WARNING: Exit price doesn't match SL (may be due to slippage)")
    
    # Timestamps
    if verbose:
        print(f"\nTimestamps:")
        print(f"  Placed: {trade.get('placed_datetime')} (Candle: {trade.get('placed_candle')})")
        print(f"  Opened: {trade.get('open_datetime')} (Candle: {trade.get('open_candle')})")
        print(f"  Closed: {trade.get('close_datetime')} (Candle: {trade.get('close_candle')})")
    
    # Verify timeline
    placed_candle = trade.get('placed_candle')
    open_candle = trade.get('open_candle')
    close_candle = trade.get('close_candle')
    
    if verbose:
        if placed_candle is not None and open_candle is not None:
            if open_candle < placed_candle:
                print(f"  ⚠️  WARNING: Opened before placed!")
        if open_candle is not None and close_candle is not None:
            if close_candle < open_candle:
                print(f"  ⚠️  WARNING: Closed before opened!")
    
    # Risk/Reward
    if verbose and tp_price and sl_price and entry_price_used:
        if side == OrderSide.BUY:
            risk = abs(entry_price_used - sl_price)
            reward = abs(tp_price - entry_price_used)
        else:  # SELL
            risk = abs(sl_price - entry_price_used)
            reward = abs(entry_price_used - tp_price)
        
        if risk > 0:
            rr_ratio = reward / risk
            print(f"\nRisk/Reward:")
            print(f"  Risk: {risk}")
            print(f"  Reward: {reward}")
            print(f"  R:R Ratio: {rr_ratio:.2f}")
    
    return {
        'trade_id': trade_id,
        'pnl_match': abs(pnl - expected_pnl) < 0.01 if (pnl is not None and expected_pnl is not None) else None,
        'exit_price_match': (
            (close_reason == 'TP' and abs(exit_price - tp_price) < 0.0001) or
            (close_reason == 'SL' and abs(exit_price - sl_price) < 0.0001)
        ) if exit_price and ((close_reason == 'TP' and tp_price) or (close_reason == 'SL' and sl_price)) else None,
        'timeline_valid': (
            (placed_candle is None or open_candle is None or open_candle >= placed_candle) and
            (open_candle is None or close_candle is None or close_candle >= open_candle)
        )
    }

def verify_all_trades(strat, verbose=False):
    """Verify all trades from a strategy instance.
    
    Args:
        strat: Strategy instance with completed trades
        verbose: If True, print detailed verification logs. If False, return boolean silently.
    
    Returns:
        bool: True if all checks passed, False otherwise
    """
    if verbose:
        print("\n" + "="*80)
        print("TRADE VERIFICATION REPORT")
        print("="*80)
    
    completed_trades = strat.get_completed_trades()
    
    if not completed_trades:
        if verbose:
            print("No completed trades to verify.")
        return True  # No trades means nothing to verify, so checks pass
    
    if verbose:
        print(f"\nTotal Completed Trades: {len(completed_trades)}")
    
    results = []
    for i, trade in enumerate(completed_trades, 1):
        result = verify_trade(trade, i, verbose=verbose)
        results.append(result)
    
    # Summary
    if verbose:
        print("\n" + "="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)
    
    pnl_matches = [r['pnl_match'] for r in results if r['pnl_match'] is not None]
    exit_matches = [r['exit_price_match'] for r in results if r['exit_price_match'] is not None]
    timeline_valid = [r['timeline_valid'] for r in results]
    
    if verbose:
        print(f"\nPnL Calculations:")
        print(f"  Verified: {len(pnl_matches)}")
        print(f"  Correct: {sum(pnl_matches)}")
        print(f"  Incorrect: {len(pnl_matches) - sum(pnl_matches)}")
        
        print(f"\nExit Prices:")
        print(f"  Verified: {len(exit_matches)}")
        print(f"  Match TP/SL: {sum(exit_matches)}")
        print(f"  Don't Match: {len(exit_matches) - sum(exit_matches)}")
        if len(exit_matches) - sum(exit_matches) > 0:
            print(f"  Note: Differences may be due to slippage")
        
        print(f"\nTimeline:")
        print(f"  Valid: {sum(timeline_valid)}")
        print(f"  Invalid: {len(timeline_valid) - sum(timeline_valid)}")
    
    # Overall validation
    all_valid = (
        (all(pnl_matches) if pnl_matches else True) and
        all(timeline_valid)
    )
    
    if verbose:
        print(f"\n{'✅ All checks passed!' if all_valid else '⚠️  Some issues found (see details above)'}")
    
    return all_valid

if __name__ == "__main__":
    print("This script should be run after a backtest.")
    print("Example usage:")
    print("  from main import backtesting")
    print("  cerebro, data = backtesting(['GBPJPY'], Timeframe.M15, ...)")
    print("  strat = cerebro.strats[0][0][0]")
    print("  from verify_trades import verify_all_trades")
    print("  # Silent mode (returns boolean):")
    print("  checks_passed = verify_all_trades(strat)")
    print("  # Verbose mode (prints detailed logs):")
    print("  checks_passed = verify_all_trades(strat, verbose=True)")

