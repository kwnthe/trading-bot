#!/usr/bin/env python3
"""
Debug script to understand multi-symbol position sizing behavior.
"""

def analyze_position_sizing_issue():
    """
    The user is right - if losses reduce capital, future losses should be smaller.
    But combined PnL is -67.91% vs sum of -31.44%.
    
    Let's check if there's a bug in current_cash calculation.
    """
    
    print("=" * 80)
    print("ANALYZING MULTI-SYMBOL POSITION SIZING")
    print("=" * 80)
    print()
    
    print("ISSUE:")
    print("-" * 80)
    print("AUDCHF alone:     +13%")
    print("EURUSD alone:     -44.44%")
    print("Simple sum:       -31.44%")
    print("Combined trading: -67.91%  ← MUCH WORSE!")
    print()
    
    print("USER'S VALID POINT:")
    print("-" * 80)
    print("If losses reduce capital, future losses should ALSO be smaller.")
    print("So combined PnL should be BETTER than sum, not worse!")
    print()
    
    print("POTENTIAL BUGS:")
    print("=" * 80)
    print()
    
    print("1. DOUBLE-COUNTING UNREALIZED PNL:")
    print("-" * 80)
    print("Current code (BaseStrategy.py line 106):")
    print("  self.current_cash = self.broker.getvalue() + self.unrealized_pnl")
    print()
    print("In Backtrader, broker.getvalue() ALREADY includes unrealized PnL!")
    print("So adding unrealized_pnl again = DOUBLE COUNTING")
    print()
    print("Example:")
    print("  - Account: $100k")
    print("  - Open AUDCHF position: -$5k unrealized")
    print("  - broker.getvalue() = $95k (already includes -$5k)")
    print("  - unrealized_pnl = -$5k")
    print("  - current_cash = $95k + (-$5k) = $90k  ← WRONG!")
    print("  - Should be: current_cash = $95k")
    print()
    print("This would make position sizing use SMALLER capital than it should,")
    print("which would make losses SMALLER, not larger...")
    print()
    
    print("2. SIMULTANEOUS POSITIONS ISSUE:")
    print("-" * 80)
    print("When you have open positions on BOTH symbols:")
    print("  - broker.getvalue() includes unrealized PnL from BOTH")
    print("  - If EURUSD has -$10k unrealized loss")
    print("  - broker.getvalue() = $90k")
    print("  - New AUDCHF trade uses $90k for position sizing")
    print("  - But if AUDCHF also loses, you're losing on BOTH simultaneously")
    print("  - This could create compounding losses")
    print()
    
    print("3. POSITION SIZING CALCULATION:")
    print("-" * 80)
    print("The issue might be:")
    print("  - When trading alone: Each trade uses full account value")
    print("  - When trading both: Each trade uses account value MINUS other symbol's losses")
    print("  - But if BOTH lose simultaneously, losses compound")
    print()
    
    print("MATHEMATICAL CHECK:")
    print("=" * 80)
    print()
    print("If we assume:")
    print("  - Start: $100k")
    print("  - EURUSD loses 44.44% → $55.56k remaining")
    print("  - AUDCHF makes 13% on remaining → $55.56k * 1.13 = $62.78k")
    print("  - Combined PnL: -37.22%")
    print()
    print("But you're seeing -67.91%, which suggests:")
    print("  - Either trades are happening in wrong order")
    print("  - Or there's a bug in position sizing")
    print("  - Or losses are compounding worse than expected")
    print()
    
    print("RECOMMENDATION:")
    print("=" * 80)
    print("1. Check if broker.getvalue() already includes unrealized PnL")
    print("2. Fix current_cash calculation if double-counting")
    print("3. Verify position sizing uses correct capital base")
    print("4. Check if simultaneous open positions cause issues")
    print()


if __name__ == '__main__':
    analyze_position_sizing_issue()


