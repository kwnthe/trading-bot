"""
Verification script to validate trading strategy PnL.
Compares results with different execution assumptions to identify unrealistic optimizations.
"""

import backtrader as bt
import sys
import os
import pandas as pd
from datetime import datetime

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.utils.config import Config, load_config
from data.csv_data_feed import CSVDataFeed
from strategies.BreakRetestStrategy import BreakRetestStrategy
from indicators.TestIndicator import TestIndicator
from src.utils.execution_simulator import RealisticExecutionBroker


def calculate_sharpe_ratio(returns, risk_free_rate=0.0):
    """Calculate Sharpe ratio from returns."""
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    excess_returns = returns - risk_free_rate
    return (excess_returns.mean() / returns.std()) * (252 ** 0.5) if returns.std() > 0 else 0.0


def calculate_max_drawdown(equity_curve):
    """Calculate maximum drawdown from equity curve."""
    if len(equity_curve) == 0:
        return 0.0
    
    peak = equity_curve[0]
    max_dd = 0.0
    
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    
    return max_dd


def run_backtest(use_realistic_execution=False, spread_pips=2.0, slippage_pips=2.0, 
                 use_cheat_on_close=False, description=""):
    """Run backtest with specified execution settings."""
    config = load_config()
    cerebro = bt.Cerebro(stdstats=False)
    
    # Configure broker execution
    if use_realistic_execution:
        cerebro.broker = RealisticExecutionBroker(
            spread_pips=spread_pips,
            slippage_pips=slippage_pips
        )
    else:
        # Use default backtrader broker (optimistic execution)
        pass
    
    if use_cheat_on_close:
        cerebro.broker.set_coc(True)
    else:
        cerebro.broker.set_coc(False)
    
    symbol = 'AUDCHF'
    csv_file_path = 'csv/AUDCHF._H1_2025-01-01_2025-09-22.csv'
    csv_feed = CSVDataFeed(csv_file_path=csv_file_path)
    data = csv_feed.get_backtrader_feed()
    cerebro.adddata(data)
    
    cerebro.addstrategy(BreakRetestStrategy, symbol=symbol, rr=Config.rr)
    cerebro.addindicator(TestIndicator)
    
    # Configure broker settings
    cerebro.broker.setcommission(commission=0.001)
    cerebro.broker.set_shortcash(True)
    cerebro.broker.set_checksubmit(False)
    cerebro.broker.set_cash(Config.initial_equity)
    
    initial_cash = cerebro.broker.getcash()
    
    results = cerebro.run()
    strat = results[0]
    final_equity = cerebro.broker.getvalue()
    
    pnl = final_equity - initial_cash
    pnl_percentage = (pnl / initial_cash) * 100
    
    # Calculate statistics
    trades = strat.trades
    if trades:
        completed_trades = [t for t in trades.values() if 'pnl' in t and t['pnl'] is not None]
        if completed_trades:
            winning_trades = [t for t in completed_trades if t['pnl'] > 0]
            losing_trades = [t for t in completed_trades if t['pnl'] < 0]
            
            win_rate = len(winning_trades) / len(completed_trades) if completed_trades else 0
            avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
            
            # Calculate equity curve for drawdown
            equity_curve = []
            current_equity = initial_cash
            for trade in sorted(completed_trades, key=lambda x: x.get('open_candle', 0)):
                equity_curve.append(current_equity)
                if 'pnl' in trade:
                    current_equity += trade['pnl']
            equity_curve.append(final_equity)
            
            max_dd = calculate_max_drawdown(equity_curve)
            
            # Calculate returns for Sharpe ratio
            returns = pd.Series([t['pnl'] / initial_cash for t in completed_trades])
            sharpe = calculate_sharpe_ratio(returns)
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            max_dd = 0
            sharpe = 0
    else:
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        max_dd = 0
        sharpe = 0
    
    # Get execution stats if using realistic broker
    execution_stats = None
    if use_realistic_execution and hasattr(cerebro.broker, 'get_execution_stats'):
        execution_stats = cerebro.broker.get_execution_stats()
    
    return {
        'description': description,
        'initial_cash': initial_cash,
        'final_equity': final_equity,
        'pnl': pnl,
        'pnl_percentage': pnl_percentage,
        'total_trades': len(completed_trades) if trades else 0,
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe,
        'total_tps': strat.counter['tp'],
        'total_sls': strat.counter['sl'],
        'execution_stats': execution_stats
    }


def main():
    """Run multiple backtests with different execution assumptions."""
    print("=" * 80)
    print("PNL VERIFICATION - Comparing Different Execution Assumptions")
    print("=" * 80)
    print()
    
    results = []
    
    # Test 1: Current setup (optimistic)
    print("Running Test 1: Current Setup (Optimistic Execution)...")
    result1 = run_backtest(
        use_realistic_execution=False,
        use_cheat_on_close=False,
        description="Current Setup (Optimistic)"
    )
    results.append(result1)
    print(f"  PnL: {result1['pnl_percentage']:.2f}%")
    print()
    
    # Test 2: With slippage and spread
    print("Running Test 2: With Slippage (2 pips) and Spread (2 pips)...")
    result2 = run_backtest(
        use_realistic_execution=True,
        spread_pips=2.0,
        slippage_pips=2.0,
        use_cheat_on_close=False,
        description="With Slippage (2p) + Spread (2p)"
    )
    results.append(result2)
    print(f"  PnL: {result2['pnl_percentage']:.2f}%")
    print()
    
    # Test 3: Higher slippage
    print("Running Test 3: Higher Slippage (5 pips) and Spread (3 pips)...")
    result3 = run_backtest(
        use_realistic_execution=True,
        spread_pips=3.0,
        slippage_pips=5.0,
        use_cheat_on_close=False,
        description="Higher Slippage (5p) + Spread (3p)"
    )
    results.append(result3)
    print(f"  PnL: {result3['pnl_percentage']:.2f}%")
    print()
    
    # Print comparison table
    print("=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)
    print()
    
    print(f"{'Test':<40} {'PnL %':<12} {'Trades':<10} {'Win Rate':<12} {'Sharpe':<10} {'Max DD':<10}")
    print("-" * 80)
    
    for r in results:
        print(f"{r['description']:<40} {r['pnl_percentage']:>10.2f}%  {r['total_trades']:>8}  "
              f"{r['win_rate']:>10.2%}  {r['sharpe_ratio']:>8.2f}  {r['max_drawdown']:>8.2%}")
    
    print()
    print("=" * 80)
    print("DETAILED STATISTICS")
    print("=" * 80)
    print()
    
    for r in results:
        print(f"\n{r['description']}:")
        print(f"  Initial Cash: ${r['initial_cash']:,.2f}")
        print(f"  Final Equity: ${r['final_equity']:,.2f}")
        print(f"  PnL: ${r['pnl']:,.2f} ({r['pnl_percentage']:.2f}%)")
        print(f"  Total Trades: {r['total_trades']}")
        print(f"  Win Rate: {r['win_rate']:.2%}")
        print(f"  Total TPs: {r['total_tps']}")
        print(f"  Total SLs: {r['total_sls']}")
        print(f"  Avg Win: ${r['avg_win']:,.2f}")
        print(f"  Avg Loss: ${r['avg_loss']:,.2f}")
        print(f"  Sharpe Ratio: {r['sharpe_ratio']:.2f}")
        print(f"  Max Drawdown: {r['max_drawdown']:.2%}")
        
        if r['execution_stats']:
            stats = r['execution_stats']
            print(f"  Execution Stats:")
            print(f"    Total Executions: {stats['total_executions']}")
            print(f"    Avg Slippage: {stats['avg_slippage']:.5f} ({stats['avg_slippage'] / 0.0001:.2f} pips)")
            print(f"    Max Slippage: {stats['max_slippage']:.5f} ({stats['max_slippage'] / 0.0001:.2f} pips)")
    
    # Calculate impact of execution costs
    if len(results) >= 2:
        print()
        print("=" * 80)
        print("EXECUTION COST IMPACT")
        print("=" * 80)
        print()
        
        optimistic_pnl = results[0]['pnl_percentage']
        realistic_pnl = results[1]['pnl_percentage']
        impact = optimistic_pnl - realistic_pnl
        
        print(f"Optimistic PnL: {optimistic_pnl:.2f}%")
        print(f"Realistic PnL (2p slippage + 2p spread): {realistic_pnl:.2f}%")
        print(f"Impact of Execution Costs: -{impact:.2f} percentage points")
        print(f"Reduction: {(impact / optimistic_pnl * 100):.1f}%" if optimistic_pnl != 0 else "N/A")
    
    # Export results to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = f"pnl_verification_{timestamp}.csv"
    
    df = pd.DataFrame(results)
    df.to_csv(csv_file, index=False)
    print(f"\nResults exported to: {csv_file}")


if __name__ == '__main__':
    main()

