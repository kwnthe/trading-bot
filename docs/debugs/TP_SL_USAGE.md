# Take Profit and Stop Loss Implementation

## Overview

Your trading bot now supports automatic take profit (TP) and stop loss (SL) functionality using **Backtrader's native bracket order support**. When a breakout position is opened, the system will automatically place TP and SL orders based on your configuration using Backtrader's built-in bracket order functionality.

## Configuration

Add these parameters to your `.env` file:

```env
# Take Profit and Stop Loss Configuration
TAKE_PROFIT_PIPS=20.0      # Take profit target in pips
STOP_LOSS_PIPS=10.0        # Stop loss in pips  
USE_TP_SL=true            # Enable/disable TP/SL functionality
```

## How It Works

### 1. **Native Bracket Orders**
- Uses Backtrader's built-in `bracket` parameter in orders
- Single order call automatically manages TP/SL lifecycle
- More reliable than manual order management

### 2. **Automatic TP/SL Placement**
- When a breakout order is placed, TP/SL are included in the bracket:
  - **Take Profit Order**: Automatically placed as limit order
  - **Stop Loss Order**: Automatically placed as stop order

### 3. **Position Types**
- **Long Positions** (Buy Breakouts):
  - TP: Sell limit order above entry price
  - SL: Sell stop order below entry price

- **Short Positions** (Sell Breakouts):
  - TP: Buy limit order below entry price  
  - SL: Buy stop order above entry price

### 4. **Native Order Management**
- Backtrader automatically handles:
  - TP/SL order placement when main order executes
  - Order cancellation when one of the bracket orders executes
  - Proper order lifecycle management

## Configuration Options

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `TAKE_PROFIT_PIPS` | 20.0 | 1.0 - 1000.0 | Take profit target in pips |
| `STOP_LOSS_PIPS` | 10.0 | 1.0 - 1000.0 | Stop loss in pips |
| `USE_TP_SL` | true | true/false | Enable/disable TP/SL functionality |

## Example Scenarios

### Scenario 1: Long Position
- Entry: 1.2500 (Buy breakout)
- TP: 1.2520 (20 pips profit)
- SL: 1.2490 (10 pips loss)

### Scenario 2: Short Position  
- Entry: 1.2500 (Sell breakout)
- TP: 1.2480 (20 pips profit)
- SL: 1.2510 (10 pips loss)

## Risk Management

- **Risk-Reward Ratio**: With default settings (TP=20, SL=10), you have a 2:1 risk-reward ratio
- **Adjustable**: You can modify the pips values to match your risk tolerance
- **Disable Option**: Set `USE_TP_SL=false` to disable automatic TP/SL placement

## Logging

The system provides detailed logging for TP/SL operations:
- `BRACKET ORDER PLACED` - When bracket orders are placed with TP/SL
- `BUY/SELL BRACKET ORDER EXECUTED` - When main order executes and TP/SL are automatically managed
- Backtrader handles TP/SL execution logging automatically

## Best Practices

1. **Risk Management**: Set SL smaller than TP for positive risk-reward
2. **Market Conditions**: Adjust TP/SL based on volatility
3. **Testing**: Backtest with different TP/SL values to find optimal settings
4. **Monitoring**: Watch the logs to ensure orders are placed correctly

## Troubleshooting

- **Orders not placed**: Check if `USE_TP_SL=true` in your config
- **Wrong prices**: Verify your pip calculation function works correctly
- **Orders not executing**: Check if the TP/SL prices are realistic for the market
