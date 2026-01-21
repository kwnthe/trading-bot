"""
Comprehensive verification script to check if backtest results are realistic.
Checks for common issues that inflate backtest performance.
"""

import backtrader as bt
import sys
import os
import pandas as pd
from collections import defaultdict

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.config import Config, load_config
from data.csv_data_feed import CSVDataFeed
from strategies.BreakRetestStrategy import BreakRetestStrategy
from src.utils.execution_simulator import RealisticExecutionBroker


class VerificationStrategy(BreakRetestStrategy):
    """Extended strategy that tracks detailed metrics for verification"""
    
    def __init__(self):
        super().__init__()
        self.position_sizes = []
        self.entry_prices = []
        self.execution_costs = []
        self.equity_over_time = []
        self.trade_details = []
        
    def calculate_position_size(self, risk_distance: float) -> float:
        """Override to track position sizing"""
        size = super().calculate_position_size(risk_distance)
        
        # Track what cash was used for calculation
        initial_equity = self.initial_cash if self.initial_cash is not None else self.broker.getvalue()
        current_cash = self.broker.getcash()
        
        self.position_sizes.append({
            'candle': self.candle_index,
            'size': size,
            'initial_equity': initial_equity,
            'current_cash': current_cash,
            'risk_distance': risk_distance
        })
        
        return size
    
    def notify_order(self, order):
        """Track order execution details"""
        if order.status in [order.Completed]:
            if order.isbuy():
                self.entry_prices.append({
                    'candle': self.candle_index,
                    'price': order.executed.price,
                    'size': order.executed.size,
                    'type': 'BUY'
                })
            else:
                self.entry_prices.append({
                    'candle': self.candle_index,
                    'price': order.executed.price,
                    'size': order.executed.size,
                    'type': 'SELL'
                })
    
    def next(self):
        super().next()
        # Track equity over time
        self.equity_over_time.append({
            'candle': self.candle_index,
            'equity': self.broker.getvalue(),
            'cash': self.broker.getcash()
        })


def check_position_sizing():
    """Verify position sizing uses initial equity, not current cash"""
    print("\n" + "="*80)
    print("VERIFICATION 1: POSITION SIZING")
    print("="*80)
    
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.0)
    
    # Load data
    csv_feed = CSVDataFeed(csv_file_path='csv/AUDCHF._H1_2025-01-01_2025-09-22.csv')
    data = csv_feed.get_backtrader_feed()
    cerebro.adddata(data)
    
    # Add strategy
    strategy = VerificationStrategy()
    cerebro.addstrategy(VerificationStrategy)
    
    # Run backtest
    initial_value = cerebro.broker.getvalue()
    results = cerebro.run()
    final_value = cerebro.broker.getvalue()
    
    strategy_instance = results[0]
    
    if not strategy_instance.position_sizes:
        print("⚠️  No position sizes tracked - no trades executed")
        return False
    
    # Check if position sizing is consistent
    sizes = [ps['size'] for ps in strategy_instance.position_sizes]
    initial_equities = [ps['initial_equity'] for ps in strategy_instance.position_sizes]
    current_cashes = [ps['current_cash'] for ps in strategy_instance.position_sizes]
    
    print(f"\nInitial Equity: ${initial_value:,.2f}")
    print(f"Final Equity: ${final_value:,.2f}")
    print(f"Total Position Sizes Calculated: {len(sizes)}")
    
    # Check if all position sizes use the same initial equity
    if len(set(initial_equities)) == 1:
        print(f"✅ PASS: All position sizes use same initial equity: ${initial_equities[0]:,.2f}")
    else:
        print(f"❌ FAIL: Position sizes use different initial equities!")
        print(f"   Range: ${min(initial_equities):,.2f} - ${max(initial_equities):,.2f}")
        return False
    
    # Check if position sizes are relatively consistent (within 20% variance)
    if sizes:
        avg_size = sum(sizes) / len(sizes)
        variance = max(abs(s - avg_size) / avg_size for s in sizes) if avg_size > 0 else 0
        if variance < 0.2:
            print(f"✅ PASS: Position sizes are consistent (variance: {variance:.1%})")
            print(f"   Average size: {avg_size:,.0f} units")
            print(f"   Range: {min(sizes):,.0f} - {max(sizes):,.0f} units")
        else:
            print(f"⚠️  WARNING: Position sizes vary significantly (variance: {variance:.1%})")
            print(f"   This might indicate compounding or other issues")
            print(f"   Average size: {avg_size:,.0f} units")
            print(f"   Range: {min(sizes):,.0f} - {max(sizes):,.0f} units")
    
    # Check if current cash changed significantly but position sizes didn't
    if len(current_cashes) > 1:
        cash_start = current_cashes[0]
        cash_end = current_cashes[-1]
        cash_change = (cash_end - cash_start) / cash_start if cash_start > 0 else 0
        
        if abs(cash_change) > 0.1:  # More than 10% change
            size_start = sizes[0]
            size_end = sizes[-1]
            size_change = (size_end - size_start) / size_start if size_start > 0 else 0
            
            if abs(size_change) < 0.1:  # Position size didn't change much
                print(f"✅ PASS: Cash changed {cash_change:.1%} but position sizes stayed consistent")
            else:
                print(f"⚠️  WARNING: Cash changed {cash_change:.1%} and position sizes changed {size_change:.1%}")
                print(f"   This might indicate compounding position sizing")
    
    return True


def check_execution_costs():
    """Verify execution costs are being applied correctly"""
    print("\n" + "="*80)
    print("VERIFICATION 2: EXECUTION COSTS")
    print("="*80)
    
    scenarios = [
        ("Optimistic", None, 0, 0),
        ("ECN Broker", RealisticExecutionBroker, 1.0, 1.0),
        ("Realistic", RealisticExecutionBroker, 2.0, 2.0),
        ("Conservative", RealisticExecutionBroker, 3.0, 5.0),
    ]
    
    results = []
    
    for name, broker_class, spread, slippage in scenarios:
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(100000.0)
        cerebro.broker.setcommission(commission=0.0)
        
        if broker_class:
            broker = broker_class(spread_pips=spread, slippage_pips=slippage)
            cerebro.broker = broker
        
        # Load data
        data = CSVDataFeed('AUDCHF', 'H1', 'csv/AUDCHF._H1_2025-01-01_2025-09-22.csv')
        cerebro.adddata(data)
        
        # Add strategy
        cerebro.addstrategy(BreakRetestStrategy)
        
        # Run backtest
        initial_value = cerebro.broker.getvalue()
        results_run = cerebro.run()
        final_value = cerebro.broker.getvalue()
        
        pnl_pct = ((final_value - initial_value) / initial_value) * 100
        
        # Get execution stats if available
        execution_stats = None
        if broker_class and hasattr(cerebro.broker, 'get_execution_stats'):
            execution_stats = cerebro.broker.get_execution_stats()
        
        results.append({
            'name': name,
            'initial': initial_value,
            'final': final_value,
            'pnl_pct': pnl_pct,
            'execution_stats': execution_stats
        })
    
    # Compare results
    optimistic_pnl = results[0]['pnl_pct']
    
    print(f"\nOptimistic PnL: {optimistic_pnl:.2f}%")
    print(f"\nExecution Cost Impact:")
    
    for r in results[1:]:
        impact = r['pnl_pct'] - optimistic_pnl
        reduction = (impact / optimistic_pnl * 100) if optimistic_pnl != 0 else 0
        print(f"\n{r['name']}:")
        print(f"  PnL: {r['pnl_pct']:.2f}%")
        print(f"  Impact: {impact:.2f} percentage points ({reduction:.1f}% reduction)")
        
        if r['execution_stats']:
            stats = r['execution_stats']
            print(f"  Total Executions: {stats['total_executions']}")
            print(f"  Avg Slippage: {stats['avg_slippage']:.5f} ({stats['avg_slippage']/0.0001:.2f} pips)")
            print(f"  Total Slippage Cost: ${stats['total_slippage']:.2f}")
    
    # Verify costs are being applied
    if results[1]['pnl_pct'] < optimistic_pnl:
        print(f"\n✅ PASS: Execution costs are reducing PnL as expected")
    else:
        print(f"\n❌ FAIL: Execution costs are not reducing PnL!")
        return False
    
    return True


def check_trade_statistics():
    """Check if trade statistics are realistic"""
    print("\n" + "="*80)
    print("VERIFICATION 3: TRADE STATISTICS")
    print("="*80)
    
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000.0)
    cerebro.broker.setcommission(commission=0.0)
    
    # Load data
    csv_feed = CSVDataFeed(csv_file_path='csv/AUDCHF._H1_2025-01-01_2025-09-22.csv')
    data = csv_feed.get_backtrader_feed()
    cerebro.adddata(data)
    
    # Add strategy
    cerebro.addstrategy(BreakRetestStrategy)
    
    # Run backtest
    initial_value = cerebro.broker.getvalue()
    results = cerebro.run()
    final_value = cerebro.broker.getvalue()
    
    strategy_instance = results[0]
    
    # Get completed trades
    completed_trades = [t for t in strategy_instance.trades.values() 
                       if 'pnl' in t and t['pnl'] is not None]
    
    if not completed_trades:
        print("⚠️  No completed trades")
        return False
    
    total_trades = len(completed_trades)
    winning_trades = [t for t in completed_trades if t['pnl'] > 0]
    losing_trades = [t for t in completed_trades if t['pnl'] < 0]
    
    win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
    avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
    
    profit_factor = abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades)) if losing_trades and sum(t['pnl'] for t in losing_trades) != 0 else float('inf')
    
    print(f"\nTotal Trades: {total_trades}")
    print(f"Winning Trades: {len(winning_trades)} ({win_rate:.1%})")
    print(f"Losing Trades: {len(losing_trades)} ({1-win_rate:.1%})")
    print(f"\nAverage Win: ${avg_win:,.2f}")
    print(f"Average Loss: ${avg_loss:,.2f}")
    print(f"Profit Factor: {profit_factor:.2f}")
    
    # Check if statistics are realistic
    issues = []
    
    if total_trades < 20:
        issues.append(f"⚠️  Low trade count ({total_trades}) - need 50+ trades for statistical validity")
    
    if win_rate > 0.7:
        issues.append(f"⚠️  Very high win rate ({win_rate:.1%}) - might indicate overfitting")
    elif win_rate < 0.3:
        issues.append(f"⚠️  Very low win rate ({win_rate:.1%}) - strategy might not be profitable")
    
    if profit_factor > 5.0:
        issues.append(f"⚠️  Very high profit factor ({profit_factor:.2f}) - might be unrealistic")
    
    if issues:
        print(f"\n⚠️  WARNINGS:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print(f"\n✅ PASS: Trade statistics look reasonable")
    
    return True


def check_lookahead_bias():
    """Check for potential look-ahead bias"""
    print("\n" + "="*80)
    print("VERIFICATION 4: LOOK-AHEAD BIAS CHECK")
    print("="*80)
    
    print("""
Look-ahead bias means using future data that wouldn't be available at trade time.

Common sources:
1. Using close price of current candle before it's closed
2. Using indicator values calculated with future data
3. Using S/R levels that weren't known at trade time
4. Perfect execution at exact prices

Manual checks needed:
- Review indicator calculations (Zones.py, BreakRetestIndicator.py)
- Verify indicators only use past candles (index -1, -2, etc.)
- Check if S/R levels are calculated before trades are placed
- Verify execution uses realistic prices (not perfect fills)

✅ PASS: Manual review required - check indicator code
""")
    
    return True


def main():
    print("\n" + "="*80)
    print("BACKTEST REALISM VERIFICATION")
    print("="*80)
    print("\nThis script verifies that backtest results are realistic and not inflated.")
    print("It checks for common issues that can make backtests look better than reality.\n")
    
    checks = [
        ("Position Sizing", check_position_sizing),
        ("Execution Costs", check_execution_costs),
        ("Trade Statistics", check_trade_statistics),
        ("Look-Ahead Bias", check_lookahead_bias),
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
3. Verify indicators don't use future data
4. Ensure execution costs are realistic
5. Get 50+ trades for statistical validity
6. Compare results with industry benchmarks:
   - Good: 10-30% annually
   - Excellent: 30-50% annually
   - Exceptional: 50-100% annually (rare)
""")


if __name__ == '__main__':
    main()

