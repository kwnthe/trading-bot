"""
Debug script to analyze execution costs and understand why the strategy is losing money.
"""

import backtrader as bt
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from bks.breakout import convert_pips_to_price
from utils.config import Config, load_config
from data.csv_data_feed import CSVDataFeed
from strategies.BreakRetestStrategy import BreakRetestStrategy
from indicators.TestIndicator import TestIndicator
from src.utils.execution_simulator import RealisticExecutionBroker
from src.utils.strategy_utils.general_utils import convert_micropips_to_price


def analyze_trade_costs():
    """Analyze the cost structure of trades."""
    config = load_config()
    
    # Example trade parameters
    initial_equity = config.initial_equity
    risk_per_trade = config.risk_per_trade
    
    print("=" * 80)
    print("TRADE COST ANALYSIS")
    print("=" * 80)
    print(f"\nInitial Equity: ${initial_equity:,.2f}")
    print(f"Risk Per Trade: {risk_per_trade * 100:.2f}%")
    print(f"Risk Amount Per Trade: ${initial_equity * risk_per_trade:,.2f}")
    
    # Example trade setup (from your logs)
    entry_price = 0.56567
    sl_price = 0.56369
    tp_price = 0.56870
    risk_distance = abs(entry_price - sl_price)
    
    print(f"\nExample Trade Setup:")
    print(f"  Entry Price: {entry_price:.5f}")
    print(f"  SL Price: {sl_price:.5f}")
    print(f"  TP Price: {tp_price:.5f}")
    print(f"  Risk Distance: {risk_distance:.5f} ({risk_distance / 0.0001:.2f} pips)")
    
    # Calculate position size
    risk_amount = initial_equity * risk_per_trade
    position_size = int(risk_amount / risk_distance)
    
    print(f"\nPosition Size: {position_size:,} units")
    print(f"Risk Amount: ${risk_amount:,.2f}")
    
    # Calculate execution costs
    spread_pips = 2.0
    slippage_pips = 2.0
    spread_price = convert_pips_to_price(spread_pips)
    slippage_price = convert_pips_to_price(slippage_pips)
    
    print(f"\nExecution Costs (per trade):")
    print(f"  Spread: {spread_pips} pips = {spread_price:.5f}")
    print(f"  Slippage: {slippage_pips} pips = {slippage_price:.5f}")
    
    # Entry costs (limit order - spread only)
    entry_cost = position_size * (spread_price / 2)
    print(f"\nEntry Cost (limit order + spread):")
    print(f"  Spread cost: {position_size:,} × {spread_price/2:.5f} = ${entry_cost:,.2f}")
    
    # Exit costs (TP limit order - spread only)
    tp_exit_cost = position_size * (spread_price / 2)
    print(f"\nTP Exit Cost (limit order + spread):")
    print(f"  Spread cost: {position_size:,} × {spread_price/2:.5f} = ${tp_exit_cost:,.2f}")
    
    # SL exit costs (stop order - slippage)
    sl_exit_cost = position_size * slippage_price
    print(f"\nSL Exit Cost (stop order + slippage):")
    print(f"  Slippage cost: {position_size:,} × {slippage_price:.5f} = ${sl_exit_cost:,.2f}")
    
    # Total costs
    total_cost_winning = entry_cost + tp_exit_cost
    total_cost_losing = entry_cost + sl_exit_cost
    
    print(f"\nTotal Execution Costs:")
    print(f"  Winning Trade (Entry + TP): ${total_cost_winning:,.2f}")
    print(f"  Losing Trade (Entry + SL): ${total_cost_losing:,.2f}")
    
    # Expected profit/loss
    profit_distance = abs(tp_price - entry_price)
    loss_distance = abs(entry_price - sl_price)
    
    gross_profit = position_size * profit_distance
    gross_loss = position_size * loss_distance
    
    print(f"\nGross P&L (before execution costs):")
    print(f"  Gross Profit (TP hit): ${gross_profit:,.2f}")
    print(f"  Gross Loss (SL hit): ${gross_loss:,.2f}")
    
    net_profit = gross_profit - total_cost_winning
    net_loss = gross_loss + total_cost_losing
    
    print(f"\nNet P&L (after execution costs):")
    print(f"  Net Profit (TP hit): ${net_profit:,.2f}")
    print(f"  Net Loss (SL hit): ${net_loss:,.2f}")
    
    # With your win rate
    win_rate = 0.3438  # 34.38%
    expected_value = (win_rate * net_profit) + ((1 - win_rate) * (-net_loss))
    
    print(f"\nExpected Value Per Trade (with {win_rate*100:.2f}% win rate):")
    print(f"  EV = ({win_rate:.2%} × ${net_profit:,.2f}) + ({1-win_rate:.2%} × -${net_loss:,.2f})")
    print(f"  EV = ${expected_value:,.2f}")
    
    # Calculate break-even
    break_even_win_rate = total_cost_losing / (gross_profit + total_cost_losing)
    print(f"\nBreak-Even Win Rate:")
    print(f"  Required: {break_even_win_rate:.2%}")
    print(f"  Current: {win_rate:.2%}")
    print(f"  Difference: {(win_rate - break_even_win_rate)*100:.2f} percentage points")
    
    # Cost as percentage of risk
    cost_percentage_of_risk = (total_cost_losing / risk_amount) * 100
    print(f"\nExecution Cost as % of Risk:")
    print(f"  Cost: ${total_cost_losing:,.2f}")
    print(f"  Risk: ${risk_amount:,.2f}")
    print(f"  Cost/Risk: {cost_percentage_of_risk:.2f}%")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if cost_percentage_of_risk > 50:
        print("⚠️  CRITICAL: Execution costs are >50% of your risk amount!")
        print("   This means execution costs are eating into your profits significantly.")
        print("\n   Solutions:")
        print("   1. Reduce position size to account for slippage")
        print("   2. Increase minimum risk distance (filter small S/R zones)")
        print("   3. Reduce risk_per_trade to lower position sizes")
        print("   4. Use limit orders more carefully (they may not always fill)")
    
    if expected_value < 0:
        print("\n⚠️  WARNING: Expected value per trade is negative!")
        print("   The strategy is not profitable with current execution costs.")
        print("   You need to either:")
        print("   - Reduce execution costs (better broker, limit orders)")
        print("   - Improve win rate or risk/reward ratio")
        print("   - Reduce position sizes")
    else:
        print(f"\n✓ Expected value is positive: ${expected_value:,.2f} per trade")
        print("  Strategy should be profitable, but execution costs are high.")


if __name__ == '__main__':
    analyze_trade_costs()


