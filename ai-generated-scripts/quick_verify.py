"""
Quick verification script - run this after your backtest
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.models.order import OrderSide

def quick_verify_trades(strat):
    """Quickly verify trade calculations."""
    completed_trades = strat.get_completed_trades()
    
    if not completed_trades:
        print("No completed trades to verify.")
        return
    
    print(f"\n{'='*80}")
    print(f"QUICK VERIFICATION - {len(completed_trades)} TRADES")
    print(f"{'='*80}\n")
    
    issues = []
    
    for i, trade in enumerate(completed_trades, 1):
        trade_id = trade.get('trade_id', 'N/A')[:8]
        side = trade.get('order_side')
        entry_price = trade.get('entry_executed_price') or trade.get('entry_price')
        exit_price = trade.get('exit_price')
        size = abs(trade.get('size', 0))
        pnl = trade.get('pnl')
        close_reason = trade.get('close_reason')
        tp = trade.get('tp')
        sl = trade.get('sl')
        
        # Calculate expected PnL
        if entry_price and exit_price:
            if side == OrderSide.BUY:
                expected_pnl = (exit_price - entry_price) * size
            else:  # SELL
                expected_pnl = (entry_price - exit_price) * size
        else:
            expected_pnl = None
        
        # Check PnL
        pnl_ok = True
        if pnl is not None and expected_pnl is not None:
            diff = abs(pnl - expected_pnl)
            if diff > 0.01:
                pnl_ok = False
                issues.append(f"Trade {trade_id}: PnL mismatch (diff: {diff:.2f})")
        
        # Check exit price matches TP/SL
        exit_ok = True
        if exit_price:
            if close_reason == 'TP' and tp:
                diff = abs(exit_price - tp)
                if diff > 0.0001:
                    exit_ok = False
                    issues.append(f"Trade {trade_id}: Exit price doesn't match TP (diff: {diff:.5f})")
            elif close_reason == 'SL' and sl:
                diff = abs(exit_price - sl)
                if diff > 0.0001:
                    exit_ok = False
                    issues.append(f"Trade {trade_id}: Exit price doesn't match SL (diff: {diff:.5f})")
        
        # Print summary for each trade
        status = "✅" if (pnl_ok and exit_ok) else "⚠️"
        print(f"{status} Trade {trade_id}: {trade.get('symbol')} {side.name if isinstance(side, OrderSide) else side}")
        print(f"   Entry: {entry_price:.5f} | Exit: {exit_price:.5f} | PnL: {pnl:.2f} | {close_reason}")
        if not pnl_ok:
            print(f"   Expected PnL: {expected_pnl:.2f} | Actual: {pnl:.2f}")
        if not exit_ok:
            expected_exit = tp if close_reason == 'TP' else sl
            print(f"   Expected Exit: {expected_exit:.5f} | Actual: {exit_price:.5f}")
    
    print(f"\n{'='*80}")
    if issues:
        print(f"⚠️  FOUND {len(issues)} ISSUES:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("✅ ALL TRADES VERIFIED CORRECTLY!")
    print(f"{'='*80}\n")

# Example: After running backtest, do:
# python quick_verify.py
# Or in Python:
# from quick_verify import quick_verify_trades
# quick_verify_trades(strat)

if __name__ == "__main__":
    print("To use this script:")
    print("1. Run your backtest first")
    print("2. Then in Python:")
    print("   from main import backtesting")
    print("   from datetime import datetime")
    print("   from src.models.timeframe import Timeframe")
    print("   cerebro, data = backtesting(['GBPJPY'], Timeframe.M15, datetime(2025,12,17), datetime(2025,12,20))")
    print("   strat = cerebro.strats[0][0][0]")
    print("   from quick_verify import quick_verify_trades")
    print("   quick_verify_trades(strat)")

