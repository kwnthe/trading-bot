"""
Simple verification script to check if backtest results are realistic.
Extends compare_execution.py with additional verification checks.
"""

import backtrader as bt
import sys
import os
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

logging.getLogger('loguru').setLevel(logging.WARNING)

from src.utils.config import Config, load_config
from data.csv_data_feed import CSVDataFeed
from strategies.BreakRetestStrategy import BreakRetestStrategy
from indicators.TestIndicator import TestIndicator
from src.utils.execution_simulator import RealisticExecutionBroker


def run_test_with_details(use_realistic=False, spread_pips=1.5, slippage_pips=1.5):
    """Run backtest and return detailed results including position sizing info."""
    config = load_config()
    cerebro = bt.Cerebro(stdstats=False)
    
    if use_realistic:
        cerebro.broker = RealisticExecutionBroker(
            spread_pips=spread_pips,
            slippage_pips=slippage_pips
        )
        cerebro.broker.setcommission(commission=0.00008)
        cerebro.broker.set_shortcash(True)
        cerebro.broker.set_checksubmit(False)
    else:
        cerebro.broker.setcommission(commission=0.00008)
        cerebro.broker.set_shortcash(True)
        cerebro.broker.set_checksubmit(False)
    
    cerebro.broker.set_coc(False)
    
    symbol = 'AUDCHF'
    csv_file_path = 'csv/AUDCHF._H1_2025-01-01_2025-09-22.csv'
    csv_feed = CSVDataFeed(csv_file_path=csv_file_path)
    data = csv_feed.get_backtrader_feed()
    cerebro.adddata(data)
    
    cerebro.addstrategy(BreakRetestStrategy, symbol=symbol, rr=Config.rr)
    cerebro.addindicator(TestIndicator)
    
    cerebro.broker.set_cash(Config.initial_equity)
    initial_cash = cerebro.broker.getcash()
    initial_equity = cerebro.broker.getvalue()
    
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        results = cerebro.run()
    
    strat = results[0]
    final_equity = cerebro.broker.getvalue()
    final_cash = cerebro.broker.getcash()
    
    pnl = final_equity - initial_equity
    pnl_percentage = (pnl / initial_equity) * 100
    
    # Get completed trades
    completed_trades = [t for t in strat.trades.values() if 'pnl' in t and t['pnl'] is not None]
    
    # Check position sizing
    position_sizes = []
    if hasattr(strat, 'initial_cash') and strat.initial_cash:
        # Verify all trades used initial_cash for position sizing
        for trade in completed_trades:
            if 'size' in trade:
                position_sizes.append(trade['size'])
    
    return {
        'pnl_percentage': pnl_percentage,
        'final_equity': final_equity,
        'initial_equity': initial_equity,
        'total_trades': len(completed_trades),
        'trades': completed_trades,
        'position_sizes': position_sizes,
        'initial_cash': initial_cash,
        'final_cash': final_cash,
        'strategy': strat
    }


def verify_position_sizing():
    """Verify that position sizing uses initial equity, not current cash"""
    print("\n" + "="*80)
    print("VERIFICATION 1: POSITION SIZING")
    print("="*80)
    
    result = run_test_with_details(use_realistic=False)
    
    strat = result['strategy']
    initial_equity = result['initial_equity']
    
    # Check if initial_cash is set and matches initial equity
    if hasattr(strat, 'initial_cash') and strat.initial_cash:
        if abs(strat.initial_cash - initial_equity) < 1.0:
            print(f"✅ PASS: initial_cash is set correctly: ${strat.initial_cash:,.2f}")
        else:
            print(f"❌ FAIL: initial_cash ({strat.initial_cash:,.2f}) doesn't match initial_equity ({initial_equity:,.2f})")
            return False
    else:
        print(f"❌ FAIL: initial_cash is not set!")
        return False
    
    # Check position sizes consistency
    if result['position_sizes']:
        sizes = result['position_sizes']
        avg_size = sum(sizes) / len(sizes)
        min_size = min(sizes)
        max_size = max(sizes)
        variance = max(abs(s - avg_size) / avg_size for s in sizes) if avg_size > 0 else 0
        
        print(f"\nPosition Size Statistics:")
        print(f"  Total trades: {len(sizes)}")
        print(f"  Average size: {avg_size:,.0f} units")
        print(f"  Range: {min_size:,.0f} - {max_size:,.0f} units")
        print(f"  Variance: {variance:.1%}")
        
        if variance < 0.2:  # Less than 20% variance
            print(f"✅ PASS: Position sizes are consistent (variance < 20%)")
            print(f"   This indicates fixed position sizing based on initial equity")
        else:
            print(f"⚠️  WARNING: Position sizes vary significantly (variance: {variance:.1%})")
            print(f"   This might indicate compounding or other issues")
            return False
    else:
        print("⚠️  No position sizes found in trades")
    
    return True


def verify_execution_costs():
    """Verify execution costs are being applied correctly"""
    print("\n" + "="*80)
    print("VERIFICATION 2: EXECUTION COSTS")
    print("="*80)
    
    result_optimistic = run_test_with_details(use_realistic=False)
    result_realistic = run_test_with_details(use_realistic=True, spread_pips=2.0, slippage_pips=2.0)
    
    optimistic_pnl = result_optimistic['pnl_percentage']
    realistic_pnl = result_realistic['pnl_percentage']
    impact = optimistic_pnl - realistic_pnl
    
    print(f"\nOptimistic PnL: {optimistic_pnl:.2f}%")
    print(f"Realistic PnL: {realistic_pnl:.2f}%")
    print(f"Impact: -{impact:.2f} percentage points")
    
    if realistic_pnl < optimistic_pnl:
        print(f"✅ PASS: Execution costs reduce PnL as expected")
        
        # Check if impact is reasonable (should be significant but not catastrophic)
        if 5 < impact < 50:
            print(f"✅ PASS: Impact is reasonable ({impact:.2f} percentage points)")
        elif impact > 50:
            print(f"⚠️  WARNING: Very high impact ({impact:.2f} percentage points)")
            print(f"   Strategy may not be profitable in live trading")
        else:
            print(f"⚠️  WARNING: Very low impact ({impact:.2f} percentage points)")
            print(f"   Execution costs might not be applied correctly")
    else:
        print(f"❌ FAIL: Execution costs are not reducing PnL!")
        return False
    
    return True


def verify_trade_statistics():
    """Check if trade statistics are realistic"""
    print("\n" + "="*80)
    print("VERIFICATION 3: TRADE STATISTICS")
    print("="*80)
    
    result = run_test_with_details(use_realistic=False)
    trades = result['trades']
    
    if not trades:
        print("⚠️  No completed trades")
        return False
    
    winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
    losing_trades = [t for t in trades if t.get('pnl', 0) < 0]
    
    total_trades = len(trades)
    win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
    avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
    
    profit_factor = abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades)) if losing_trades and sum(t['pnl'] for t in losing_trades) != 0 else float('inf')
    
    print(f"\nTrade Statistics:")
    print(f"  Total Trades: {total_trades}")
    print(f"  Winning Trades: {len(winning_trades)} ({win_rate:.1%})")
    print(f"  Losing Trades: {len(losing_trades)} ({1-win_rate:.1%})")
    print(f"  Average Win: ${avg_win:,.2f}")
    print(f"  Average Loss: ${avg_loss:,.2f}")
    print(f"  Profit Factor: {profit_factor:.2f}")
    
    issues = []
    
    if total_trades < 20:
        issues.append(f"Low trade count ({total_trades}) - need 50+ for statistical validity")
    
    if win_rate > 0.7:
        issues.append(f"Very high win rate ({win_rate:.1%}) - might indicate overfitting")
    elif win_rate < 0.3:
        issues.append(f"Very low win rate ({win_rate:.1%}) - strategy might not be profitable")
    
    if profit_factor > 5.0:
        issues.append(f"Very high profit factor ({profit_factor:.2f}) - might be unrealistic")
    
    if issues:
        print(f"\n⚠️  WARNINGS:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print(f"\n✅ PASS: Trade statistics look reasonable")
    
    return True


def verify_results_realism():
    """Check if overall results are realistic"""
    print("\n" + "="*80)
    print("VERIFICATION 4: RESULTS REALISM")
    print("="*80)
    
    result_optimistic = run_test_with_details(use_realistic=False)
    result_realistic = run_test_with_details(use_realistic=True, spread_pips=2.0, slippage_pips=2.0)
    
    optimistic_pnl = result_optimistic['pnl_percentage']
    realistic_pnl = result_realistic['pnl_percentage']
    
    print(f"\nOptimistic PnL: {optimistic_pnl:.2f}%")
    print(f"Realistic PnL: {realistic_pnl:.2f}%")
    
    # Check against industry benchmarks
    # For 9 months of data, annualize: (pnl / 9) * 12
    annualized_optimistic = (optimistic_pnl / 9) * 12
    annualized_realistic = (realistic_pnl / 9) * 12
    
    print(f"\nAnnualized (estimated):")
    print(f"  Optimistic: {annualized_optimistic:.1f}%")
    print(f"  Realistic: {annualized_realistic:.1f}%")
    
    print(f"\nIndustry Benchmarks:")
    print(f"  Good: 10-30% annually")
    print(f"  Excellent: 30-50% annually")
    print(f"  Exceptional: 50-100% annually (rare)")
    
    if annualized_realistic < 0:
        print(f"\n❌ FAIL: Strategy is not profitable with realistic execution")
        return False
    elif annualized_realistic < 10:
        print(f"\n✅ PASS: Results are realistic but modest")
        print(f"   Strategy shows {annualized_realistic:.1f}% annualized return")
    elif annualized_realistic < 50:
        print(f"\n✅ PASS: Results are realistic and good")
        print(f"   Strategy shows {annualized_realistic:.1f}% annualized return")
    elif annualized_realistic < 100:
        print(f"\n⚠️  WARNING: Results are very high ({annualized_realistic:.1f}% annualized)")
        print(f"   Verify there's no look-ahead bias or overfitting")
    else:
        print(f"\n❌ FAIL: Results are unrealistically high ({annualized_realistic:.1f}% annualized)")
        print(f"   Likely issues: look-ahead bias, overfitting, or bugs")
        return False
    
    return True


def main():
    print("\n" + "="*80)
    print("BACKTEST REALISM VERIFICATION")
    print("="*80)
    print("\nThis script verifies that backtest results are realistic and not inflated.")
    print("It checks for common issues that can make backtests look better than reality.\n")
    
    checks = [
        ("Position Sizing", verify_position_sizing),
        ("Execution Costs", verify_execution_costs),
        ("Trade Statistics", verify_trade_statistics),
        ("Results Realism", verify_results_realism),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n❌ ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False
    
    # Summary
    print("\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nOverall: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n✅ All checks passed! Your backtest results appear realistic.")
    else:
        print("\n⚠️  Some checks failed. Review the issues above.")
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print("""
1. Test on out-of-sample data (different time periods)
2. Test on different symbols  
3. Verify indicators don't use future data (manual code review)
4. Ensure execution costs are realistic
5. Get 50+ trades for statistical validity
6. Compare results with industry benchmarks
""")


if __name__ == '__main__':
    main()

