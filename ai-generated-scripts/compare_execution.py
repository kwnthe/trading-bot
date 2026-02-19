"""
Quick comparison script to see the impact of execution costs on your strategy.
Run this to compare optimistic vs realistic execution.
"""

import backtrader as bt
import sys
import os
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Suppress loguru INFO logs
logging.getLogger('loguru').setLevel(logging.WARNING)

from src.utils.config import Config, load_config
from data.csv_data_feed import CSVDataFeed
from strategies.BreakRetestStrategy import BreakRetestStrategy
from indicators.TestIndicator import TestIndicator
from src.utils.execution_simulator import RealisticExecutionBroker


def run_test(use_realistic=False, spread_pips=1.5, slippage_pips=1.5):
    """Run backtest with specified execution settings."""
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
        print(f"Running with REALISTIC execution (Spread: {spread_pips}p, Slippage: {slippage_pips}p)...")
    else:
        print(f"Running with OPTIMISTIC execution (no slippage/spread)...")

    cerebro.broker.set_coc(False)

    symbol = 'EURUSD'
    csv_file_path = 'csv/AUDCHF._H1_2025-01-01_2025-09-22.csv'

    csv_feed = CSVDataFeed(csv_file_path=csv_file_path)
    data = csv_feed.get_backtrader_feed()
    cerebro.adddata(data)

    cerebro.addstrategy(BreakRetestStrategy, symbol=symbol, rr=Config.rr)
    cerebro.addindicator(TestIndicator)

    if not use_realistic:
        cerebro.broker.setcommission(commission=0.00008)
        cerebro.broker.set_shortcash(True)
        cerebro.broker.set_checksubmit(False)

    cerebro.broker.set_cash(Config.initial_equity)
    initial_cash = cerebro.broker.getcash()

    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        results = cerebro.run()

    strat = results[0]
    final_equity = cerebro.broker.getvalue()

    pnl = final_equity - initial_cash
    pnl_percentage = (pnl / initial_cash) * 100

    completed_trades = [t for t in strat.trades.values() if 'pnl' in t and t['pnl'] is not None]
    total_trades = len(completed_trades)
    winning_trades = len([t for t in completed_trades if t['pnl'] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0

    return {
        'pnl_percentage': pnl_percentage,
        'final_equity': final_equity,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'win_rate': win_rate,
        'tps': strat.counter['tp'],
        'sls': strat.counter['sl']
    }


if __name__ == '__main__':
    print("\n" + "="*80)
    print("EXECUTION COST COMPARISON")
    print("="*80)

    # Test 1: Optimistic (current setup)
    result_optimistic = run_test(use_realistic=False)

    # Test 2: ECN Broker (1p spread, 1p slippage)
    result_ecn = run_test(use_realistic=True, spread_pips=1.0, slippage_pips=1.0)

    # Test 3: Realistic (2p spread, 2p slippage)
    result_realistic = run_test(use_realistic=True, spread_pips=2.0, slippage_pips=2.0)

    # Test 4: Conservative (3p spread, 5p slippage)
    result_conservative = run_test(use_realistic=True, spread_pips=3.0, slippage_pips=5.0)

    print("\n" + "="*80)
    print("COMPARISON RESULTS")
    print("="*80)
    print(f"\n{'Scenario':<40} {'PnL %':<15} {'Final Equity':<15} {'Trades':<10} {'Win Rate':<10}")
    print("-"*95)

    def line(label, r):
        print(f"{label:<40} {r['pnl_percentage']:>13.2f}%  "
              f"${r['final_equity']:>13,.2f}  {r['total_trades']:>8}  {r['win_rate']:>8.2f}%")

    line("Optimistic (Current)", result_optimistic)
    line("ECN Broker (1p spread, 1p slippage)", result_ecn)
    line("Realistic (2p spread, 2p slippage)", result_realistic)
    line("Conservative (3p spread, 5p slippage)", result_conservative)

    impact_ecn = result_optimistic['pnl_percentage'] - result_ecn['pnl_percentage']
    impact_realistic = result_optimistic['pnl_percentage'] - result_realistic['pnl_percentage']
    impact_conservative = result_optimistic['pnl_percentage'] - result_conservative['pnl_percentage']

    print("\n" + "="*80)
    print("EXECUTION COST IMPACT")
    print("="*80)

    print("\n⚠️  The 'Optimistic' scenario assumes perfect execution with no spread or slippage —")
    print("   This is unrealistic and should only be used as an upper bound.\n")

    # Function for profitability messages
    def profit_label(r):
        return "YES" if r['pnl_percentage'] > 0 else "NO"

    def impact_block(name, r, impact):
        print(f"{name}: {r['pnl_percentage']:.2f}%")
        print(f"  📉 Reduction from optimistic: -{impact:.2f} points "
              f"({(impact / result_optimistic['pnl_percentage'] * 100):.1f}% lower)")
        print(f"  {'✅ Still profitable: YES' if r['pnl_percentage'] > 0 else '❌ Not profitable: NO'} "
              f"({r['pnl_percentage']:.2f}%)")
        print(f"  📊 Win Rate: {r['win_rate']:.2f}% "
              f"({r['winning_trades']}/{r['total_trades']})\n")

    impact_block("ECN Broker (1p/1p)", result_ecn, impact_ecn)
    impact_block("Realistic (2p/2p)", result_realistic, impact_realistic)
    impact_block("Conservative (3p/5p)", result_conservative, impact_conservative)

    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    # Clear and honest logic
    if result_ecn['pnl_percentage'] > 0:
        print(f"✅ Strategy is profitable with an ECN broker ({result_ecn['pnl_percentage']:.2f}%).")
    else:
        print(f"❌ Strategy is NOT profitable even with ECN execution ({result_ecn['pnl_percentage']:.2f}%).")

    if result_realistic['pnl_percentage'] > 0:
        print(f"✅ Strategy is profitable under typical broker conditions ({result_realistic['pnl_percentage']:.2f}%).")
    else:
        print(f"❌ Strategy is NOT profitable under realistic broker conditions ({result_realistic['pnl_percentage']:.2f}%).")
