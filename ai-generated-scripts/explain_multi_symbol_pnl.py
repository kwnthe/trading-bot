#!/usr/bin/env python3
"""
Demonstrates why multi-symbol PnL doesn't equal the sum of individual PnLs
due to compounding position sizing.
"""

def simulate_trading_scenarios():
    """Simulate different trading scenarios to show compounding effects."""
    
    initial_capital = 100000
    risk_per_trade = 0.01  # 1% per trade
    
    print("=" * 80)
    print("MULTI-SYMBOL PNL EXPLANATION")
    print("=" * 80)
    print()
    
    # Scenario 1: AUDCHF alone
    print("SCENARIO 1: Trading AUDCHF alone")
    print("-" * 80)
    audchf_capital = initial_capital
    audchf_trades = [
        ("Trade 1", 0.05),   # +5% gain
        ("Trade 2", -0.02),  # -2% loss
        ("Trade 3", 0.08),   # +8% gain
        ("Trade 4", 0.02),   # +2% gain
    ]
    
    for trade_name, pnl_pct in audchf_trades:
        risk_amount = audchf_capital * risk_per_trade
        trade_pnl = risk_amount * (pnl_pct / risk_per_trade)  # Simplified: assume 1:1 RR
        audchf_capital += trade_pnl
        print(f"  {trade_name}: Capital=${audchf_capital:,.2f}, Trade PnL=${trade_pnl:,.2f}")
    
    audchf_final = audchf_capital
    audchf_pnl_pct = ((audchf_final - initial_capital) / initial_capital) * 100
    print(f"  Final Capital: ${audchf_final:,.2f}")
    print(f"  Total PnL: {audchf_pnl_pct:.2f}%")
    print()
    
    # Scenario 2: EURUSD alone
    print("SCENARIO 2: Trading EURUSD alone")
    print("-" * 80)
    eurusd_capital = initial_capital
    eurusd_trades = [
        ("Trade 1", -0.15),  # -15% loss
        ("Trade 2", -0.10),  # -10% loss
        ("Trade 3", -0.12),  # -12% loss
        ("Trade 4", -0.07),  # -7% loss
    ]
    
    for trade_name, pnl_pct in eurusd_trades:
        risk_amount = eurusd_capital * risk_per_trade
        trade_pnl = risk_amount * (pnl_pct / risk_per_trade)
        eurusd_capital += trade_pnl
        print(f"  {trade_name}: Capital=${eurusd_capital:,.2f}, Trade PnL=${trade_pnl:,.2f}")
    
    eurusd_final = eurusd_capital
    eurusd_pnl_pct = ((eurusd_final - initial_capital) / initial_capital) * 100
    print(f"  Final Capital: ${eurusd_final:,.2f}")
    print(f"  Total PnL: {eurusd_pnl_pct:.2f}%")
    print()
    
    # Scenario 3: Both symbols simultaneously (interleaved trades)
    print("SCENARIO 3: Trading BOTH symbols simultaneously")
    print("-" * 80)
    print("  (Trades happen in sequence, losses reduce capital for next trade)")
    print()
    
    combined_capital = initial_capital
    all_trades = [
        ("AUDCHF Trade 1", 0.05),
        ("EURUSD Trade 1", -0.15),
        ("AUDCHF Trade 2", -0.02),
        ("EURUSD Trade 2", -0.10),
        ("AUDCHF Trade 3", 0.08),
        ("EURUSD Trade 3", -0.12),
        ("AUDCHF Trade 4", 0.02),
        ("EURUSD Trade 4", -0.07),
    ]
    
    for trade_name, pnl_pct in all_trades:
        risk_amount = combined_capital * risk_per_trade
        trade_pnl = risk_amount * (pnl_pct / risk_per_trade)
        combined_capital += trade_pnl
        print(f"  {trade_name}: Capital=${combined_capital:,.2f}, Trade PnL=${trade_pnl:,.2f}")
    
    combined_final = combined_capital
    combined_pnl_pct = ((combined_final - initial_capital) / initial_capital) * 100
    print(f"  Final Capital: ${combined_final:,.2f}")
    print(f"  Total PnL: {combined_pnl_pct:.2f}%")
    print()
    
    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"AUDCHF alone:     {audchf_pnl_pct:+.2f}%")
    print(f"EURUSD alone:     {eurusd_pnl_pct:+.2f}%")
    print(f"Simple sum:       {audchf_pnl_pct + eurusd_pnl_pct:+.2f}%")
    print(f"Combined trading: {combined_pnl_pct:+.2f}%")
    print()
    print("KEY INSIGHT:")
    print("-" * 80)
    print("When trading multiple symbols simultaneously:")
    print("1. Losses from one symbol REDUCE capital available for the other")
    print("2. This creates COMPOUNDING losses - each loss makes subsequent")
    print("   trades smaller, but the percentage losses still apply")
    print("3. The combined PnL is WORSE than the sum because:")
    print("   - Early losses reduce capital")
    print("   - Later trades (even winners) are smaller")
    print("   - The compounding effect amplifies the negative impact")
    print()
    print("Example:")
    print("  If EURUSD loses early, AUDCHF trades use smaller position sizes")
    print("  Even if AUDCHF wins, the wins are smaller because capital was")
    print("  already reduced by EURUSD losses.")
    print()
    print("This is why:")
    print(f"  Combined PnL ({combined_pnl_pct:.2f}%) < Sum ({audchf_pnl_pct + eurusd_pnl_pct:.2f}%)")
    print()
    print("=" * 80)
    print("SOLUTION OPTIONS:")
    print("=" * 80)
    print("1. Use FIXED position sizing (based on initial capital)")
    print("   - Prevents compounding effects")
    print("   - Combined PnL will equal sum of individual PnLs")
    print()
    print("2. Use SEPARATE accounts per symbol")
    print("   - Each symbol trades independently")
    print("   - No cross-symbol capital reduction")
    print()
    print("3. Keep current approach (compounding)")
    print("   - More realistic for real trading")
    print("   - But understand that combined PnL won't equal sum")


if __name__ == '__main__':
    simulate_trading_scenarios()


