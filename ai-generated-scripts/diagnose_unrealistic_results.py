"""
Diagnostic script to identify why backtest results seem too good to be true.
Checks for common issues like compounding position sizing, look-ahead bias, etc.
"""

import backtrader as bt
import sys
import os
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

logging.getLogger('loguru').setLevel(logging.WARNING)

from utils.config import Config, load_config
from data.csv_data_feed import CSVDataFeed
from strategies.BreakRetestStrategy import BreakRetestStrategy
from indicators.TestIndicator import TestIndicator
from src.utils.execution_simulator import RealisticExecutionBroker


def analyze_position_sizing_compounding():
    """Check if position sizing is compounding unrealistically"""
    print("\n" + "="*80)
    print("ISSUE 1: COMPOUNDING POSITION SIZING")
    print("="*80)
    
    print("""
Your strategy uses getcash() for position sizing, which means:
- As account grows, position sizes increase
- This creates exponential growth
- Early losses = small positions
- Later wins = huge positions

Example:
- Trade 1: $100k account → $1k risk → 500k units
- Trade 10: $150k account → $1.5k risk → 750k units  
- Trade 20: $200k account → $2k risk → 1M units
- Trade 30: $300k account → $3k risk → 1.5M units

This is COMPOUNDING RISK, not fixed risk!
""")
    
    print("✅ FIX: Use fixed initial equity for position sizing")
    print("   Change: current_cash → initial_cash")
    print("   This keeps position sizes constant regardless of account growth")


def analyze_trade_frequency():
    """Check if trade frequency is realistic"""
    print("\n" + "="*80)
    print("ISSUE 2: LOW TRADE FREQUENCY")
    print("="*80)
    
    print("""
You have only 30 trades over 9 months (~3 trades/month).

Problems:
- Each trade has massive impact
- Can't verify statistical significance
- High variance (few trades = unreliable results)
- One lucky streak can make strategy look amazing

Realistic trading:
- Should have 50-200+ trades for statistical validity
- More trades = more reliable results
- Less variance = more confidence
""")


def analyze_execution_costs():
    """Check if execution costs are realistic"""
    print("\n" + "="*80)
    print("ISSUE 3: EXECUTION COSTS MAY BE TOO LOW")
    print("="*80)
    
    print("""
With compounding position sizing:
- Early trades: Small positions → Small costs
- Later trades: Huge positions → But costs still based on spread/slippage

The execution simulator adds costs, but:
- Costs are per-unit (spread/slippage in pips)
- With huge positions, costs should be massive
- But if most wins happen late with huge positions, costs don't offset gains

Check:
- Are execution costs actually being applied?
- Are costs proportional to position size?
- Are costs eating into profits enough?
""")


def run_detailed_analysis():
    """Run backtest and analyze trade-by-trade"""
    print("\n" + "="*80)
    print("DETAILED TRADE ANALYSIS")
    print("="*80)
    
    config = load_config()
    cerebro = bt.Cerebro(stdstats=False)
    
    symbol = 'AUDCHF'
    csv_file_path = 'csv/AUDCHF._H1_2025-01-01_2025-09-22.csv'
    csv_feed = CSVDataFeed(csv_file_path=csv_file_path)
    data = csv_feed.get_backtrader_feed()
    cerebro.adddata(data)
    
    cerebro.addstrategy(BreakRetestStrategy, symbol=symbol, rr=Config.rr)
    cerebro.addindicator(TestIndicator)
    
    cerebro.broker.setcommission(commission=0.00008)
    cerebro.broker.set_shortcash(True)
    cerebro.broker.set_checksubmit(False)
    cerebro.broker.set_coc(False)
    cerebro.broker.set_cash(Config.initial_equity)
    
    initial_cash = cerebro.broker.getcash()
    
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        results = cerebro.run()
    
    strat = results[0]
    final_equity = cerebro.broker.getvalue()
    
    completed_trades = [t for t in strat.trades.values() if 'pnl' in t and t['pnl'] is not None]
    
    if not completed_trades:
        print("No completed trades found!")
        return
    
    # Sort trades by open candle
    completed_trades.sort(key=lambda x: x.get('open_candle', 0))
    
    print(f"\nInitial Equity: ${initial_cash:,.2f}")
    print(f"Final Equity: ${final_equity:,.2f}")
    print(f"Total Trades: {len(completed_trades)}")
    print(f"\nTrade-by-Trade Analysis:")
    print("-"*80)
    
    current_equity = initial_cash
    position_sizes = []
    pnls = []
    
    for i, trade in enumerate(completed_trades[:10], 1):  # Show first 10 trades
        open_candle = trade.get('open_candle', 'N/A')
        close_candle = trade.get('close_candle', 'N/A')
        pnl = trade.get('pnl', 0)
        size = trade.get('size', 0)
        order_side = trade.get('order_side', 'UNKNOWN')
        
        # Calculate position size at time of trade
        price = trade.get('price', 0) or 0
        sl = trade.get('sl', 0) or 0
        risk_distance = abs(price - sl) if price and sl else 0
        if risk_distance > 0:
            risk_amount = current_equity * Config.risk_per_trade
            calculated_size = int(risk_amount / risk_distance)
        else:
            calculated_size = size
        
        position_sizes.append(size)
        pnls.append(pnl)
        
        print(f"\nTrade {i} (Candle {open_candle} → {close_candle}):")
        print(f"  Equity before: ${current_equity:,.2f}")
        print(f"  Position size: {size:,} units (calculated: {calculated_size:,})")
        print(f"  PnL: ${pnl:,.2f} ({pnl/current_equity*100:.2f}%)")
        print(f"  Equity after: ${current_equity + pnl:,.2f}")
        
        current_equity += pnl
    
    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)
    
    if len(position_sizes) > 1:
        first_size = position_sizes[0]
        last_size = position_sizes[-1]
        size_growth = (last_size / first_size - 1) * 100 if first_size > 0 else 0
        print(f"\nPosition Size Growth:")
        print(f"  First trade: {first_size:,} units")
        print(f"  Last trade: {last_size:,} units")
        print(f"  Growth: {size_growth:.1f}%")
        
        if size_growth > 50:
            print(f"\n⚠️  WARNING: Position sizes grew by {size_growth:.1f}%!")
            print("   This is COMPOUNDING RISK - not realistic for fixed risk strategy")
    
    if len(pnls) > 0:
        avg_pnl = sum(pnls) / len(pnls)
        print(f"\nAverage PnL per trade: ${avg_pnl:,.2f}")
        
        if avg_pnl > initial_cash * 0.05:  # More than 5% per trade
            print(f"\n⚠️  WARNING: Average PnL is {avg_pnl/initial_cash*100:.1f}% per trade!")
            print("   This is extremely high - suggests compounding or unrealistic assumptions")


def check_for_lookahead_bias():
    """Check for potential look-ahead bias"""
    print("\n" + "="*80)
    print("ISSUE 4: POTENTIAL LOOK-AHEAD BIAS")
    print("="*80)
    
    print("""
Look-ahead bias means using future data in calculations.

Common sources:
1. Using close price of current candle before it's closed
2. Using indicator values calculated with future data
3. Using S/R levels that weren't known at trade time
4. Perfect execution at exact prices

Check your indicators:
- Are they calculated only with past data?
- Do they use current candle's close before it's finalized?
- Are S/R levels known at the time of trade?

If yes → Look-ahead bias → Unrealistic results
""")


def main():
    print("\n" + "="*80)
    print("DIAGNOSING UNREALISTIC BACKTEST RESULTS")
    print("="*80)
    
    print("""
Your results show:
- Optimistic: 716% PnL
- ECN Broker: 86% PnL  
- Realistic: 75% PnL

These numbers are EXTREMELY high and likely unrealistic.
Let's identify why...
""")
    
    analyze_position_sizing_compounding()
    analyze_trade_frequency()
    analyze_execution_costs()
    check_for_lookahead_bias()
    
    run_detailed_analysis()
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    print("""
1. FIX COMPOUNDING POSITION SIZING:
   - Use initial_cash instead of getcash()
   - This keeps position sizes constant
   - More realistic for fixed-risk strategy

2. INCREASE TRADE FREQUENCY:
   - Test on more data
   - More trades = more reliable results
   - Need 50-200+ trades for statistical validity

3. VERIFY EXECUTION COSTS:
   - Check if costs are actually being applied
   - Costs should be proportional to position size
   - With huge positions, costs should be massive

4. CHECK FOR LOOK-AHEAD BIAS:
   - Verify indicators use only past data
   - Ensure S/R levels are known at trade time
   - No future data in calculations

5. TEST ON OUT-OF-SAMPLE DATA:
   - Use different time periods
   - Use different symbols
   - Verify strategy works consistently

After fixes, expect:
- More realistic PnL (10-30% annually, not 700%+)
- More consistent results across different data
- Better alignment with real-world trading
""")


if __name__ == '__main__':
    main()

