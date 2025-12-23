# Slippage Issue Explanation

## Problem

The SELL(183) trade showed a PnL of **-1469.86** even though the calculated risk was only **970.30**. This discrepancy of **~499.56** was caused by **slippage**, not spreads.

## Root Cause

### How Backtrader Executes Stop Orders

When a stop loss order is triggered in backtrader, it executes at the **worst possible price** within that candle:

- **For BUY stop orders** (closing SELL positions): Executes at the **candle HIGH**
- **For SELL stop orders** (closing BUY positions): Executes at the **candle LOW**

This simulates realistic market conditions where stop orders can experience slippage.

### SELL(183) Trade Analysis

- **Entry Price**: 0.5288700000
- **Stop Loss Price**: 0.5298800000
- **Expected Risk**: 970.30 (1% of equity)
- **Actual Execution Price**: 0.53040 (candle high when stop was triggered)
- **Actual PnL**: -1469.86
- **Slippage**: 0.00052 (5.2 pips) worse than stop loss price
- **Extra Loss**: 499.56

The stop loss was triggered when price hit 0.5298800000, but backtrader executed the BUY stop order at the candle high of 0.53040, causing the additional loss.

## Solution

### 1. Slippage Buffer in Position Sizing

Added a `slippage_pips` configuration parameter that accounts for slippage when calculating position size. This ensures the actual risk (including slippage) matches your intended risk percentage.

**Configuration** (add to `.env`):
```env
SLIPPAGE_PIPS=2.0  # Slippage buffer in pips (default: 2.0)
```

The position sizing calculation now uses:
```
adjusted_risk_distance = risk_distance + slippage_price
position_size = risk_amount / adjusted_risk_distance
```

This reduces position size slightly to account for slippage, ensuring your actual risk stays within your target percentage.

### 2. Enhanced Logging

The trade logging now shows:
- Actual execution price
- Expected stop loss price (for SL trades)
- Slippage in pips

Example output:
```
❌  SELL(183 -> 184) Close Price: 0.5294400000, Execution: 0.5304000000, SL Price: 0.5298800000, Actual: 0.5304000000, Slippage: 5.2 pips, PnL: -1469.86, Equity: 95560.04
```

## Recommendations

1. **Set appropriate slippage buffer**: For H1 timeframe, 2-5 pips is reasonable. Adjust based on:
   - Market volatility
   - Timeframe (lower timeframes = more slippage)
   - Currency pair (exotic pairs = more slippage)

2. **Monitor slippage**: Review the logs to see actual slippage and adjust `SLIPPAGE_PIPS` accordingly.

3. **Consider using limit orders for TP**: Take profit orders can use limit orders which execute at better prices, reducing slippage on winning trades.

## Technical Details

### Position Sizing Formula

**Before (without slippage):**
```python
risk_distance = abs(stop_price - stop_loss)
position_size = risk_amount / risk_distance
```

**After (with slippage):**
```python
risk_distance = abs(stop_price - stop_loss)
slippage_price = convert_pips_to_price(slippage_pips)
adjusted_risk_distance = risk_distance + slippage_price
position_size = risk_amount / adjusted_risk_distance
```

This ensures that even if the stop loss executes with slippage, your actual risk remains close to your target percentage.

