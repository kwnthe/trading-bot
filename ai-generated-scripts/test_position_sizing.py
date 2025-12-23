#!/usr/bin/env python3
"""
Test script to verify position sizing calculation based on risk percentage.
"""

def test_position_sizing():
    """Test the position sizing calculation logic"""
    
    # Test parameters
    current_equity = 10000.0  # $10,000 account
    risk_per_trade = 0.01     # 1% risk per trade (as decimal)
    stop_price = 0.7000       # Entry price
    stop_loss = 0.6950        # Stop loss price
    
    # Calculate risk amount
    risk_amount = current_equity * risk_per_trade
    print(f"Account Equity: ${current_equity:,.2f}")
    print(f"Risk Per Trade: {risk_per_trade*100:.1f}%")
    print(f"Risk Amount: ${risk_amount:.2f}")
    
    # Calculate risk distance
    risk_distance = abs(stop_price - stop_loss)
    print(f"Stop Price: {stop_price:.4f}")
    print(f"Stop Loss: {stop_loss:.4f}")
    print(f"Risk Distance: {risk_distance:.4f}")
    
    # Calculate position size
    units = int(risk_amount / risk_distance) if risk_distance > 0 else 100000
    units = max(units, 1000)  # Minimum 1000 units
    
    print(f"Calculated Units: {units:,}")
    
    # Verify the calculation
    actual_risk = units * risk_distance
    actual_risk_percentage = (actual_risk / current_equity) * 100
    
    print(f"Actual Risk Amount: ${actual_risk:.2f}")
    print(f"Actual Risk Percentage: {actual_risk_percentage:.2f}%")
    
    # Test with different scenarios
    print("\n" + "="*50)
    print("Testing different scenarios:")
    print("="*50)
    
    scenarios = [
        (10000, 0.01, 0.7000, 0.6950),  # 1% risk, 50 pip stop
        (10000, 0.02, 0.7000, 0.6950),  # 2% risk, 50 pip stop
        (10000, 0.01, 0.7000, 0.6980),  # 1% risk, 20 pip stop
        (5000, 0.01, 0.7000, 0.6950),   # 1% risk, smaller account
    ]
    
    for equity, risk_decimal, entry, sl in scenarios:
        risk_amt = equity * risk_decimal
        risk_dist = abs(entry - sl)
        units_calc = int(risk_amt / risk_dist) if risk_dist > 0 else 100000
        units_calc = max(units_calc, 1000)
        actual_risk = units_calc * risk_dist
        actual_pct = (actual_risk / equity) * 100
        
        print(f"Equity: ${equity:,}, Risk Per Trade: {risk_decimal*100:.1f}%, Entry: {entry:.4f}, SL: {sl:.4f}")
        print(f"  -> Units: {units_calc:,}, Actual Risk: {actual_pct:.2f}%")
        print()

if __name__ == "__main__":
    test_position_sizing()
