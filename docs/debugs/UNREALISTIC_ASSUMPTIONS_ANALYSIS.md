# Analysis: Unrealistic Assumptions Causing High Returns

## Summary

After fixing compounding position sizing, your 75% PnL in 9 months is still high. Here are the **unrealistic assumptions** I found:

## Critical Issues Found

### 1. **Limit Orders Always Fill** ⚠️ CRITICAL

**The Problem:**
- `limit_fill_probability` parameter exists but is **never used**
- Limit orders fill even if price **never touches** the limit price
- Lines 71-73, 80-83: "Price didn't touch limit - in backtrader this still executes"

**Impact:**
- Entry limit orders fill even if price gaps over them
- TP limit orders fill even if price gaps under them
- Unrealistic fills = unrealistic profits

**Realistic Behavior:**
- Limit orders should only fill if price **touches** the limit price
- If price gaps over/under limit, order should **not fill**
- This reduces fill rate and profits

**Expected Impact:**
- Some trades won't fill → fewer trades → lower total PnL
- More realistic fill rates (70-90% instead of 100%)

---

### 2. **Perfect Limit Order Execution** ⚠️ MEDIUM

**The Problem:**
- Limit orders execute at limit price + spread/2
- But in reality, limit orders might fill at **better** prices (limit or better)
- Current implementation always charges spread, even if filled at better price

**Impact:**
- Slightly higher execution costs than reality
- But this makes results MORE conservative, not less

**Note:** This is actually good - it's conservative, not optimistic.

---

### 3. **Low Trade Frequency** ⚠️ HIGH

**The Problem:**
- Only **30 trades over 9 months** (~3 trades/month)
- High variance = unreliable results
- One lucky streak can make strategy look amazing

**Impact:**
- Results are highly variable
- Can't verify statistical significance
- Strategy might not work on different data

**Realistic Trading:**
- Should have **50-200+ trades** for statistical validity
- More trades = more reliable results

---

### 4. **Commission Rate** ✅ CHECKED

**Current:** 0.00008 (0.008% per trade)

**Status:** This is reasonable for forex ECN brokers
- Typical forex commission: 0.00005 - 0.0001 (0.005% - 0.01%)
- Your rate is within normal range

**Impact:** Commission is properly applied, not causing unrealistic results.

---

### 5. **Execution Costs Scaling** ✅ CHECKED

**Status:** Execution costs scale properly with position sizes
- Spread: Applied per unit
- Slippage: Applied per unit
- Costs grow with position sizes (compounding)

**Impact:** Execution costs are realistic and properly scaled.

---

## Recommended Fixes

### Fix 1: Implement Limit Fill Probability (CRITICAL)

Update `execution_simulator.py` to check if price touched limit before filling:

```python
if order.exectype == bt.Order.Limit:
    limit_price = order.price
    
    if order.isbuy():
        # Check if price touched limit
        if current_low is not None and current_low <= limit_price:
            # Price touched limit - fill order
            execution_price = limit_price + (spread_price / 2)
        else:
            # Price didn't touch limit - don't fill
            # In backtrader, we can't prevent fill, but we can make it expensive
            # Or skip execution entirely
            return None  # Don't fill if price didn't touch
    else:
        # Similar for sell limits
        if current_high is not None and current_high >= limit_price:
            execution_price = limit_price - (spread_price / 2)
        else:
            return None  # Don't fill if price didn't touch
```

**Expected Impact:**
- 10-30% of limit orders won't fill
- Reduces total trades by 10-30%
- More realistic fill rates

---

### Fix 2: Use Limit Fill Probability Parameter

Actually use the `limit_fill_probability` parameter:

```python
if order.exectype == bt.Order.Limit:
    limit_price = order.price
    
    # Check if price touched limit
    price_touched = False
    if order.isbuy() and current_low is not None:
        price_touched = current_low <= limit_price
    elif not order.isbuy() and current_high is not None:
        price_touched = current_high >= limit_price
    
    if price_touched:
        # Price touched limit - check fill probability
        if random.random() < self.limit_fill_probability:
            # Fill order
            execution_price = ...
        else:
            # Don't fill (price touched but order didn't fill due to liquidity)
            return None
    else:
        # Price didn't touch limit - don't fill
        return None
```

**Expected Impact:**
- More realistic fill rates (70-95% instead of 100%)
- Reduces profits by 5-30%

---

## Expected Results After Fixes

**Current:**
- Realistic: 75% PnL (with compounding, 30 trades)

**After Fix 1 (Limit Fill Check):**
- Realistic: 50-65% PnL (10-30% fewer fills)

**After Fix 2 (Fill Probability):**
- Realistic: 40-55% PnL (more realistic fill rates)

**With More Trades (50-200+):**
- More reliable results
- Better statistical significance
- Lower variance

---

## Other Considerations

### Look-Ahead Bias ✅ CHECKED
- Indicators appear to use only past data
- No obvious look-ahead bias detected

### Data Quality ⚠️ UNKNOWN
- Testing on single symbol (AUDCHF)
- Single time period (9 months)
- Need to test on more data for validation

### Survivorship Bias ⚠️ UNKNOWN
- Strategy might only work on this specific pair/period
- Need to test on different pairs/periods

---

## Conclusion

**Main Issues:**
1. ✅ **Limit orders always fill** (CRITICAL - needs fix)
2. ⚠️ **Low trade frequency** (30 trades - need more data)
3. ✅ **Execution costs** (properly applied)
4. ✅ **Commission** (reasonable rate)

**Recommended Actions:**
1. **Fix limit order fill logic** (most important)
2. **Test on more data** (get 50-200+ trades)
3. **Test on different pairs/periods** (verify robustness)

After fixing limit order fills, expect **40-55% PnL** instead of 75%, which is more realistic for a profitable strategy.


