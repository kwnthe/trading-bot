# Summary: Why Orders Didn't Execute (Margin Issue)

## Problem
BUY LIMIT orders didn't execute even when price touched the entry point. The order status changed to "Margin" (rejected due to insufficient funds).

## Root Cause
- Using `BacktestingBroker` with `leverage=100` (1:100 leverage)
- Backtrader's default broker (`BackBroker`) requires **full position value** in cash, not margin
- Example: Buying 2,309 units at $66.045 = $152,500 position value
  - With 1:100 leverage, only **$1,525 margin** is needed
  - Backtrader checks for **$152,500 cash** → rejects with "Margin" status

## Why This Happens
Backtrader's `_execute()` method checks cash via `getcash()` and expects full position value. With leverage, you only need margin (1% with 1:100 leverage), but the parent class doesn't account for leverage.

## Solution Needed
Override `_execute()` to:
1. **Temporarily inflate cash** before calling `super()._execute()` so parent sees enough cash
2. **After execution**, adjust cash to only deduct the margin (not full position value)
3. Override `_check_cash()` to check margin instead of full position value

## Current Setup
- Broker: `BacktestingBroker(spread_pips=spread_pips, leverage=100)`
- File: `/Users/konstantinos/projects/trading-bot/trading-bot/src/brokers/backtesting_broker.py`
- The broker already has leverage support, but the cash adjustment logic in `_execute()` needs to work correctly

## Key Point
With leverage, you only need **margin** (1% with 1:100 leverage), but backtrader's parent checks for **full position value**. The fix is to temporarily show enough cash during the check, then adjust to actual margin after execution.
