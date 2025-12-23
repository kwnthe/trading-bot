# PnL Verification Guide

This guide explains how to verify if your trading strategy's PnL is realistic and identify potential issues with backtesting assumptions.

## Issues That Can Inflate PnL

### 1. **Cheat on Close (set_coc)**
- **Status**: Currently DISABLED (commented out in `main.py:62`)
- **Impact**: Allows closing positions on the same bar they're opened
- **Fix**: Keep `set_coc(False)` or commented out

### 2. **No Slippage Simulation**
- **Status**: Default backtrader execution (optimistic)
- **Impact**: Orders execute at best possible prices
- **Fix**: Use `RealisticExecutionBroker` with slippage simulation

### 3. **No Spread Simulation**
- **Status**: Trading at mid-price
- **Impact**: No bid/ask spread costs
- **Fix**: Use `RealisticExecutionBroker` with spread simulation

### 4. **Optimistic Limit Order Execution**
- **Status**: Limit orders execute at best price even if price gaps
- **Impact**: Unrealistic fills
- **Fix**: Use realistic execution broker

## Verification Tools

### 1. Run Verification Script

The `verify_pnl.py` script compares PnL with different execution assumptions:

```bash
python verify_pnl.py
```

This will run three backtests:
1. **Current Setup** (Optimistic) - No slippage, no spread
2. **With Slippage (2p) + Spread (2p)** - Realistic execution
3. **Higher Slippage (5p) + Spread (3p)** - Conservative execution

The script outputs:
- PnL comparison across all scenarios
- Statistical metrics (Sharpe ratio, max drawdown, win rate)
- Execution cost impact analysis
- CSV export of results

### 2. Enhanced Trade Export

The strategy now exports detailed execution information to CSV:

**New CSV Fields:**
- `entry_order_price` - Original limit order price
- `entry_execution_price` - Actual execution price
- `entry_slippage` - Slippage on entry (in price units and pips)
- `tp_execution_price` - TP execution price
- `tp_slippage` - Slippage on TP
- `sl_execution_price` - SL execution price
- `sl_slippage` - Slippage on SL
- `total_slippage` - Total slippage cost per trade

**Statistics Added:**
- Max Drawdown
- Sharpe Ratio
- Average slippage per trade
- Total slippage cost

### 3. Real-Time Execution Tracking

The strategy now logs execution details for each trade:
- Entry order price vs execution price
- TP/SL execution prices
- Slippage in pips
- Total execution costs

## Using Realistic Execution

To enable realistic execution simulation in your backtest:

```python
from src.utils.execution_simulator import RealisticExecutionBroker

# In main():
cerebro.broker = RealisticExecutionBroker(
    spread_pips=2.0,      # Bid/ask spread in pips
    slippage_pips=2.0     # Slippage on stop orders in pips
)
```

## Interpreting Results

### Red Flags (Unrealistic PnL):
1. **>50% PnL** over 9 months without realistic execution costs
2. **Win rate >70%** with 1:2 risk-reward ratio
3. **Sharpe ratio >3** without accounting for execution costs
4. **Large difference** between optimistic and realistic PnL (>20 percentage points)

### Realistic Expectations:
- **Forex spreads**: 1-3 pips for major pairs, 2-5 pips for minor pairs
- **Slippage**: 1-3 pips in normal conditions, 5-10+ pips during volatility
- **Commission**: 0.01-0.02% per trade (already included)
- **Typical Sharpe**: 1.0-2.0 for good strategies, >2.0 is exceptional

## Example Output

```
================================================================================
PNL VERIFICATION - Comparing Different Execution Assumptions
================================================================================

Test                                    PnL %      Trades    Win Rate    Sharpe    Max DD
--------------------------------------------------------------------------------
Current Setup (Optimistic)              96.00%        45      65.00%      2.50     15.00%
With Slippage (2p) + Spread (2p)        78.50%        45      62.00%      2.10     18.00%
Higher Slippage (5p) + Spread (3p)      65.20%        45      60.00%      1.85     20.00%

EXECUTION COST IMPACT
Optimistic PnL: 96.00%
Realistic PnL (2p slippage + 2p spread): 78.50%
Impact of Execution Costs: -17.50 percentage points
Reduction: 18.2%
```

## Next Steps

1. **Run verification script** to see impact of execution costs
2. **Review CSV exports** to identify trades with high slippage
3. **Adjust strategy** if execution costs significantly reduce PnL
4. **Consider**:
   - Filtering trades during high volatility
   - Adjusting position sizing for slippage
   - Using limit orders more carefully
   - Testing on different timeframes

## Files Modified

- `main.py` - Added statistical metrics display
- `src/strategies/BreakRetestStrategy.py` - Added execution tracking
- `src/strategies/BaseStrategy.py` - Enhanced CSV export
- `src/utils/execution_simulator.py` - New realistic execution broker
- `verify_pnl.py` - New verification script

