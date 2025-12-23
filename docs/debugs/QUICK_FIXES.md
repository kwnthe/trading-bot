# Quick Fixes to Improve Profitability

## Immediate Actions (Copy-Paste Ready)

### Fix 1: Increase Slippage Buffer ✅ ALREADY APPLIED

**File**: `src/strategies/BaseStrategy.py`  
**Line**: ~107  
**Status**: ✅ Already updated to 3.0 pips

This reduces position sizes by ~15-20% to account for slippage.

---

### Fix 2: Reduce Risk Per Trade (Optional)

**File**: `.env`  
**Action**: Change this line:

```env
RISK_PER_TRADE=0.005  # Changed from 0.01 (1% to 0.5%)
```

**Impact**: Halves position sizes and execution costs

---

### Fix 3: Increase Minimum Risk Distance (Optional)

**File**: `src/strategies/BreakRetestStrategy.py`  
**Line**: ~179  
**Change**:
```python
min_risk_distance_micropips = 20.0  # Increased from 10.0
```

**Impact**: Filters out smaller S/R zones where execution costs are proportionally higher

---

## Test After Changes

Run this to see the impact:

```bash
python compare_execution.py
```

**Target**: Realistic PnL should be **0-30%** (positive or close to break-even)

---

## If Still Negative

Try combining Fixes 1 + 2:
- Slippage buffer: 3.0 pips ✅ (already done)
- Risk per trade: 0.5% (add this)

This should get you to **20-40% PnL** with realistic execution.

