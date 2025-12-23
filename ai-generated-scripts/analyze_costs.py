"""
Analyze execution costs to understand why strategy is still losing money.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from bks.breakout import convert_pips_to_price
from utils.config import Config, load_config
from src.utils.strategy_utils.general_utils import convert_micropips_to_price

def analyze():
    config = load_config()
    
    print("=" * 80)
    print("EXECUTION COST ANALYSIS")
    print("=" * 80)
    
    # Example trade from your logs
    initial_equity = config.initial_equity  # $100,000
    risk_per_trade = config.risk_per_trade  # 1%
    
    entry_price = 0.56567
    sl_price = 0.56369
    tp_price = 0.56870
    risk_distance = abs(entry_price - sl_price)  # ~20 pips
    
    print(f"\nTrade Setup:")
    print(f"  Initial Equity: ${initial_equity:,.2f}")
    print(f"  Risk Per Trade: {risk_per_trade * 100:.2f}%")
    print(f"  Entry: {entry_price:.5f}")
    print(f"  SL: {sl_price:.5f}")
    print(f"  TP: {tp_price:.5f}")
    print(f"  Risk Distance: {risk_distance:.5f} ({risk_distance / 0.0001:.2f} pips)")
    
    # Position sizing WITHOUT slippage adjustment
    risk_amount = initial_equity * risk_per_trade
    position_size_no_adj = int(risk_amount / risk_distance)
    
    # Position sizing WITH slippage adjustment (2 pips)
    slippage_pips = 2.0
    slippage_price = convert_pips_to_price(slippage_pips)
    adjusted_risk_distance = risk_distance + slippage_price
    position_size_with_adj = int(risk_amount / adjusted_risk_distance)
    
    print(f"\nPosition Sizing:")
    print(f"  Without slippage adjustment: {position_size_no_adj:,} units")
    print(f"  With slippage adjustment (2p): {position_size_with_adj:,} units")
    print(f"  Reduction: {((position_size_no_adj - position_size_with_adj) / position_size_no_adj * 100):.1f}%")
    
    # Execution costs
    spread_pips = 2.0
    slippage_pips = 2.0
    spread_price = convert_pips_to_price(spread_pips)
    slippage_price = convert_pips_to_price(slippage_pips)
    
    print(f"\nExecution Costs (per pip):")
    print(f"  Spread: {spread_pips} pips = {spread_price:.5f}")
    print(f"  Slippage: {slippage_pips} pips = {slippage_price:.5f}")
    
    # Calculate costs WITH slippage-adjusted position size
    entry_cost = position_size_with_adj * (spread_price / 2)  # Limit order: spread/2
    tp_exit_cost = position_size_with_adj * (spread_price / 2)  # Limit order: spread/2
    sl_exit_cost = position_size_with_adj * slippage_price  # Stop order: slippage
    
    print(f"\nExecution Costs Per Trade (with slippage-adjusted sizing):")
    print(f"  Entry (limit + spread/2): {position_size_with_adj:,} × {spread_price/2:.5f} = ${entry_cost:,.2f}")
    print(f"  TP Exit (limit + spread/2): {position_size_with_adj:,} × {spread_price/2:.5f} = ${tp_exit_cost:,.2f}")
    print(f"  SL Exit (stop + slippage): {position_size_with_adj:,} × {slippage_price:.5f} = ${sl_exit_cost:,.2f}")
    
    total_cost_winning = entry_cost + tp_exit_cost
    total_cost_losing = entry_cost + sl_exit_cost
    
    print(f"\nTotal Execution Costs:")
    print(f"  Winning Trade (Entry + TP): ${total_cost_winning:,.2f}")
    print(f"  Losing Trade (Entry + SL): ${total_cost_losing:,.2f}")
    
    # Expected profit/loss
    profit_distance = abs(tp_price - entry_price)
    loss_distance = abs(entry_price - sl_price)
    
    gross_profit = position_size_with_adj * profit_distance
    gross_loss = position_size_with_adj * loss_distance
    
    print(f"\nGross P&L (before execution costs):")
    print(f"  Gross Profit (TP hit): ${gross_profit:,.2f}")
    print(f"  Gross Loss (SL hit): ${gross_loss:,.2f}")
    
    net_profit = gross_profit - total_cost_winning
    net_loss = gross_loss + total_cost_losing
    
    print(f"\nNet P&L (after execution costs):")
    print(f"  Net Profit (TP hit): ${net_profit:,.2f}")
    print(f"  Net Loss (SL hit): ${net_loss:,.2f}")
    
    # With your win rate
    win_rate = 11 / 32  # 11 TPs, 21 SLs from your results
    expected_value = (win_rate * net_profit) + ((1 - win_rate) * (-net_loss))
    
    print(f"\nExpected Value Per Trade:")
    print(f"  Win Rate: {win_rate:.2%} ({11} wins, {21} losses)")
    print(f"  EV = ({win_rate:.2%} × ${net_profit:,.2f}) + ({1-win_rate:.2%} × -${net_loss:,.2f})")
    print(f"  EV = ${expected_value:,.2f}")
    
    # Cost as percentage of risk
    cost_percentage_of_risk = (total_cost_losing / risk_amount) * 100
    print(f"\nExecution Cost Analysis:")
    print(f"  Cost per losing trade: ${total_cost_losing:,.2f}")
    print(f"  Intended risk: ${risk_amount:,.2f}")
    print(f"  Cost as % of risk: {cost_percentage_of_risk:.2f}%")
    
    # Break-even analysis
    print(f"\nBreak-Even Analysis:")
    print(f"  Required win rate: {(total_cost_losing / (gross_profit + total_cost_losing)):.2%}")
    print(f"  Current win rate: {win_rate:.2%}")
    print(f"  Difference: {(win_rate - (total_cost_losing / (gross_profit + total_cost_losing)))*100:.2f} percentage points")
    
    # Total impact
    print(f"\nTotal Impact (32 trades):")
    print(f"  Expected total P&L: ${expected_value * 32:,.2f}")
    print(f"  Expected PnL %: {(expected_value * 32 / initial_equity) * 100:.2f}%")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if expected_value < 0:
        print("⚠️  Strategy is still unprofitable with current execution costs.")
        print("\nPossible solutions:")
        print("1. Increase slippage buffer in position sizing (from 2p to 3-4p)")
        print("2. Reduce risk_per_trade (from 1% to 0.5%)")
        print("3. Increase minimum risk distance (filter smaller S/R zones)")
        print("4. Use tighter spreads (better broker - 1p instead of 2p)")
        print("5. Improve win rate or risk/reward ratio")
    else:
        print(f"✓ Strategy should be profitable: ${expected_value:,.2f} per trade")
        print("  If results show losses, check execution simulator implementation.")

if __name__ == '__main__':
    analyze()


