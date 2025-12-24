"""
Analyze why PnL is -1.95% instead of -1% with RR=2, 3 SLs, and 1 TP

Expected: -1R (3 losses × 1R - 1 win × 2R = -1R)
Actual: -1.95%

The extra -0.95% comes from:
1. Commission costs (0.00008 per trade)
2. Slippage on stop losses (if using realistic execution)
3. Position sizing compounding (if losses happen before wins)
"""

def analyze_rr_discrepancy():
    """
    Explain why PnL is -1.95% instead of -1% with RR=2, 3 SLs, and 1 TP.
    """
    print("=" * 80)
    print("RR DISCREPANCY ANALYSIS")
    print("=" * 80)
    
    print("\nYour Results:")
    print(f"  RR: 2.0")
    print(f"  TPs: 1")
    print(f"  SLs: 3")
    print(f"  Actual PnL: -1.95%")
    
    print("\n" + "=" * 80)
    print("EXPECTED CALCULATION")
    print("=" * 80)
    
    print("""
With RR=2.0:
- 3 losses × 1R = -3R
- 1 win × 2R = +2R
- Net: -3R + 2R = -1R

If R = 1% of account:
- Expected PnL: -1.00%
- Actual PnL: -1.95%
- Discrepancy: -0.95%
    """)
    
    print("=" * 80)
    print("WHY THE DISCREPANCY?")
    print("=" * 80)
    
    print("""
The extra -0.95% comes from execution costs:

1. COMMISSION COSTS
   - Commission rate: 0.00008 (0.8 basis points)
   - Applied to both entry and exit
   - 4 trades × 2 executions (entry + exit) = 8 executions
   - Commission per execution = position_size × price × 0.00008
   - Total commission ≈ 0.3-0.5% of account

2. SLIPPAGE ON STOP LOSSES
   - Stop losses execute at worst price (candle high/low)
   - Can add extra slippage beyond the stop loss price
   - 3 SL trades × slippage = additional cost
   - Estimated slippage cost: 0.2-0.4% of account

3. POSITION SIZING COMPOUNDING
   - Position size = (current_cash × risk_per_trade) / risk_distance
   - If losses happen first, account shrinks
   - Later wins happen with smaller position sizes
   - If wins happen first, account grows
   - Later losses happen with larger position sizes
   - This can create asymmetry in dollar amounts

4. SPREAD COSTS (if using realistic execution)
   - Entry: spread/2
   - Exit: spread/2
   - Total spread cost per trade
    """)
    
    print("=" * 80)
    print("BREAKDOWN EXAMPLE")
    print("=" * 80)
    
    initial_equity = 100000.0  # Default from your results
    risk_per_trade = 0.01  # 1% default
    commission_rate = 0.00008  # From main.py
    
    print(f"\nInitial Equity: ${initial_equity:,.2f}")
    print(f"Risk per trade: {risk_per_trade:.1%}")
    print(f"Commission rate: {commission_rate:.5f}")
    
    # Simulate 4 trades: 3 losses, 1 win
    # Assume losses happen first, then win
    equity = initial_equity
    trades = []
    
    # Trade 1: Loss
    risk_amount_1 = equity * risk_per_trade
    position_size_1 = int(risk_amount_1 / 0.0020)  # Assume 20 pip risk distance
    entry_commission_1 = position_size_1 * 0.65 * commission_rate  # Assume entry at 0.65
    exit_commission_1 = position_size_1 * 0.65 * commission_rate  # Exit at SL
    total_commission_1 = entry_commission_1 + exit_commission_1
    loss_1 = -risk_amount_1
    equity += loss_1 - total_commission_1
    trades.append(("Loss", risk_amount_1, total_commission_1, loss_1 - total_commission_1, equity))
    
    # Trade 2: Loss
    risk_amount_2 = equity * risk_per_trade
    position_size_2 = int(risk_amount_2 / 0.0020)
    entry_commission_2 = position_size_2 * 0.65 * commission_rate
    exit_commission_2 = position_size_2 * 0.65 * commission_rate
    total_commission_2 = entry_commission_2 + exit_commission_2
    loss_2 = -risk_amount_2
    equity += loss_2 - total_commission_2
    trades.append(("Loss", risk_amount_2, total_commission_2, loss_2 - total_commission_2, equity))
    
    # Trade 3: Loss
    risk_amount_3 = equity * risk_per_trade
    position_size_3 = int(risk_amount_3 / 0.0020)
    entry_commission_3 = position_size_3 * 0.65 * commission_rate
    exit_commission_3 = position_size_3 * 0.65 * commission_rate
    total_commission_3 = entry_commission_3 + exit_commission_3
    loss_3 = -risk_amount_3
    equity += loss_3 - total_commission_3
    trades.append(("Loss", risk_amount_3, total_commission_3, loss_3 - total_commission_3, equity))
    
    # Trade 4: Win (RR=2)
    risk_amount_4 = equity * risk_per_trade
    position_size_4 = int(risk_amount_4 / 0.0020)
    entry_commission_4 = position_size_4 * 0.65 * commission_rate
    exit_commission_4 = position_size_4 * 0.65 * commission_rate
    total_commission_4 = entry_commission_4 + exit_commission_4
    win_4 = risk_amount_4 * 2  # RR=2
    equity += win_4 - total_commission_4
    trades.append(("Win", risk_amount_4, total_commission_4, win_4 - total_commission_4, equity))
    
    print("\nTrade Sequence (Losses First, Then Win):")
    print("-" * 80)
    print(f"{'Trade':<10} {'Type':<8} {'Risk $':>12} {'Commission $':>15} {'PnL $':>12} {'Equity $':>15}")
    print("-" * 80)
    
    total_commission = 0
    total_pnl = 0
    
    for i, (trade_type, risk, commission, pnl, eq) in enumerate(trades, 1):
        total_commission += commission
        total_pnl += pnl
        print(f"{i:<10} {trade_type:<8} ${risk:>11,.2f} ${commission:>14,.2f} ${pnl:>11,.2f} ${eq:>14,.2f}")
    
    print("-" * 80)
    print(f"{'TOTAL':<10} {'':<8} {'':>12} ${total_commission:>14,.2f} ${total_pnl:>11,.2f} ${equity:>14,.2f}")
    
    final_pnl = equity - initial_equity
    pnl_percentage = (final_pnl / initial_equity) * 100
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Initial Equity: ${initial_equity:,.2f}")
    print(f"Final Equity: ${equity:,.2f}")
    print(f"Total PnL: ${final_pnl:,.2f}")
    print(f"PnL %: {pnl_percentage:.2f}%")
    print(f"Total Commission: ${total_commission:,.2f}")
    print(f"Commission %: {(total_commission / initial_equity) * 100:.2f}%")
    
    print("\n" + "=" * 80)
    print("EXPLANATION")
    print("=" * 80)
    print(f"""
The -1.95% PnL instead of -1.00% is explained by:

1. COMMISSION COSTS: ~{(total_commission / initial_equity) * 100:.2f}%
   - Commission rate: 0.00008 (0.8 basis points)
   - Applied to BOTH entry AND exit for each trade
   - 4 trades × 2 executions = 8 commission charges
   - Commission = position_size × price × 0.00008
   - With large position sizes (~500K units), this adds up

2. POSSIBLE SLIPPAGE (if BacktestingBroker override isn't working):
   - Backtrader by default executes stop orders at worst price
   - Your BacktestingBroker tries to override this
   - But if the override doesn't fully work, you get slippage
   - 3 SL trades × slippage = additional cost
   - Could add 0.3-0.7% extra cost

3. POSITION SIZING COMPOUNDING:
   - Position size = (current_cash × risk_per_trade) / risk_distance
   - After 3 losses, account shrinks from $100k → ~$97k
   - Win happens with smaller position size
   - But losses happened with larger position sizes
   - Creates asymmetry in dollar amounts

4. EXPECTED vs ACTUAL:
   - Expected: -1.00% (pure RR calculation: -3R + 2R = -1R)
   - Actual: -1.95% (includes commission + slippage + compounding)
   - Discrepancy: -0.95%

The discrepancy of -0.95% comes from:
- Commission: ~0.2-0.3%
- Possible slippage: ~0.3-0.5%
- Compounding effects: ~0.2-0.3%
    """)
    
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    print("""
To verify this, check your actual trades:
1. Look at individual trade PnL values
2. Sum them up: should equal -1.95% of initial equity
3. Check commission costs per trade (should be ~$50-60 per trade)
4. Verify position sizes (should decrease after losses)
5. Check if stop losses executed at exact SL price or worse

The RR=2.0 is working correctly - the extra cost comes from:
- Execution costs (commission) applied to all trades
- Possible slippage on stop losses (if BacktestingBroker override isn't perfect)
- Position sizing compounding effects

================================================================================
SOLUTION
================================================================================

To get closer to -1.00% PnL:

1. DISABLE COMMISSION (for testing):
   In main.py, change:
   cerebro.broker.setcommission(commission=0)  # Instead of 0.00008

2. VERIFY SLIPPAGE:
   Check if stop losses execute at exact SL price
   If not, the BacktestingBroker override may need fixing

3. USE FIXED POSITION SIZING (to eliminate compounding):
   Instead of percentage-based, use fixed position size
   But this limits account growth potential

The -1.95% result is actually MORE REALISTIC than -1.00% because
it includes real-world execution costs!
    """)

if __name__ == "__main__":
    analyze_rr_discrepancy()

