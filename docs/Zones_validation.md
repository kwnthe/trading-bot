# Zones.extend_srs Logic Validation

## Mathematical Invariant
**Must always hold**: `support < resistance` (when both are valid numbers)

## State Space Analysis

### Before Extension (after lines 71-78)
Possible states:
- A: support=nan, resistance=nan
- B: support=val, resistance=nan  
- C: support=nan, resistance=val
- D: support=val1, resistance=val2 (where val1 < val2, guaranteed by lines 73-78)

### After Extension (lines 88-96)
State transitions:
- A → A (nothing to extend)
- B → B or D (support stays, resistance might extend)
- C → C or D (resistance stays, support might extend)  
- D → D (both stay, nothing to extend)

### After Validation (lines 98-120)
Only executes if both are valid (not nan).

## Edge Cases Tested

### Case 1: Support extended, resistance set this bar, conflict
- Previous: support=70, resistance=72
- Current: Sets resistance=68 (BEARISH), support=nan
- Extension: support=70 (extended), resistance=68 (set)
- Result: 70 >= 68 → Clear support ✓

### Case 2: Resistance extended, support set this bar, conflict  
- Previous: support=70, resistance=72
- Current: Sets support=75 (BULLISH), resistance=nan
- Extension: support=75 (set), resistance=72 (extended)
- Result: 75 >= 72 → Clear resistance ✓

### Case 3: Both extended, conflict (weekend gap)
- Previous: support=70, resistance=72
- Current: No new S/R set, both nan
- Extension: support=70, resistance=72
- Gap scenario: Price jumps to 80, but previous values still valid relative to each other
- Result: 70 < 72 → Both kept ✓

### Case 4: Both extended, conflict after huge gap
- Previous: support=70, resistance=72  
- Current: No new S/R, both nan
- Extension: support=70, resistance=72
- Huge gap down: Price at 65, but values still 70 < 72
- Result: 70 < 72 → Both kept (valid relative to each other) ✓

### Case 5: Both set this bar, conflict (shouldn't happen)
- Lines 71-78 prevent this, but if it occurs:
- Result: Distance-based clearing ✓

### Case 6: Equality case (support == resistance)
- Line 101 uses `>=` which catches equality
- Result: Treated as invalid, cleared ✓

### Case 7: Distance tie (support_distance == resistance_distance)
- Line 117: `if support_distance > resistance_distance`
- If equal, clears resistance (else branch)
- Result: One cleared (arbitrary but consistent) ✓

## Potential Issues Found

### Issue 1: Distance tie handling
If `support_distance == resistance_distance`, resistance is always cleared.
This is arbitrary but consistent. Consider: Is this the desired behavior?

### Issue 2: Both set this bar case
The else branch (line 111) handles "both were extended or both were set this bar".
If both were set this bar, lines 71-78 should have prevented conflict.
But if it somehow occurs, distance-based clearing is reasonable.

## Verification Checklist

- [x] Extension logic correctly tracks which values were extended
- [x] Validation only runs when both values are valid
- [x] Conflict resolution prioritizes values set this bar over extended
- [x] Distance-based tiebreaker for both-extended case
- [x] Equality case (support == resistance) handled
- [x] All branches covered
- [x] No division by zero or invalid math operations
- [x] Weekend gap scenarios handled

## Conclusion
Logic is **CORRECT** and handles all edge cases appropriately.
