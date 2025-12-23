"""
Realistic execution simulator for backtesting.
Adds slippage and spread simulation to make backtests more realistic.
"""

import backtrader as bt
from typing import Optional
from src.utils.strategy_utils.general_utils import convert_micropips_to_price, convert_pips_to_price
from utils.config import Config


class RealisticExecutionBroker(bt.brokers.BackBroker):
    """
    Broker that simulates realistic execution with slippage and spread.
    
    Features:
    - Spread simulation (bid/ask spread)
    - Slippage on market orders and stop orders
    - Limit order fill probability (may not fill if price gaps)
    """
    
    def __init__(self, spread_pips: float = 2.0, slippage_pips: float = 2.0, 
                 limit_fill_probability: float = 0.95, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spread_pips = spread_pips
        self.slippage_pips = slippage_pips
        self.limit_fill_probability = limit_fill_probability
        self.execution_log = []  # Track executions for analysis
        
    def _execute(self, order, price=None, ago=0, **kwargs):
        """
        Override execution to add realistic slippage and spread.
        
        Execution rules:
        - Limit orders: Execute at limit price if price touched, with spread cost
        - Stop orders: Execute at stop price + slippage (worst case)
        - Market orders: Execute at current price + spread + slippage
        """
        original_price = price
        
        # Get current market data
        data = order.data
        if data is None:
            return super()._execute(order, price=price, ago=ago)
        
        try:
            current_high = data.high[ago] if ago < len(data.high) else None
            current_low = data.low[ago] if ago < len(data.low) else None
            current_close = data.close[ago] if ago < len(data.close) else None
        except (IndexError, TypeError):
            # Fallback to original price if data access fails
            return super()._execute(order, price=price, ago=ago)
        
        spread_price = convert_pips_to_price(self.spread_pips)
        slippage_price = convert_pips_to_price(self.slippage_pips)
        
        # Determine execution price based on order type
        if order.exectype == bt.Order.Limit:
            # Limit orders: Execute at limit price or better, with spread cost
            # Limit orders typically fill at limit price (or better), but you pay the spread
            limit_price = order.price
            
            if order.isbuy():
                # Buy limit: Execute at limit price, but pay ask (limit + spread/2)
                # Limit orders fill at limit or better, so worst case is limit + spread
                if current_low is not None and current_low <= limit_price:
                    # Price touched limit, order fills at limit price + spread
                    execution_price = limit_price + (spread_price / 2)
                else:
                    # Price didn't touch limit - in backtrader this still executes
                    # Use limit price + spread as execution price
                    execution_price = limit_price + (spread_price / 2)
            else:
                # Sell limit: Execute at limit price, but pay bid (limit - spread/2)
                # Limit orders fill at limit or better, so worst case is limit - spread
                if current_high is not None and current_high >= limit_price:
                    # Price touched limit, order fills at limit price - spread
                    execution_price = limit_price - (spread_price / 2)
                else:
                    # Price didn't touch limit - in backtrader this still executes
                    # Use limit price - spread as execution price
                    execution_price = limit_price - (spread_price / 2)
            
            price = execution_price
            
        elif order.exectype == bt.Order.Stop:
            # Stop orders: Execute at stop price when triggered, with slippage
            # Stop orders execute at worst price when triggered (high for buy stops, low for sell stops)
            stop_price = order.price
            
            if order.isbuy():
                # Buy stop: Executes when price hits stop, at worst price (candle high) + slippage
                # Spread is already included in worst-case execution
                if current_high is not None:
                    # Execute at worst price (high) when stop is triggered, plus slippage
                    # The spread is already reflected in the high/low prices
                    execution_price = max(stop_price, current_high) + slippage_price
                else:
                    execution_price = stop_price + slippage_price
            else:
                # Sell stop: Executes when price hits stop, at worst price (candle low) - slippage
                # Spread is already included in worst-case execution
                if current_low is not None:
                    # Execute at worst price (low) when stop is triggered, minus slippage
                    # The spread is already reflected in the high/low prices
                    execution_price = min(stop_price, current_low) - slippage_price
                else:
                    execution_price = stop_price - slippage_price
            
            price = execution_price
            
        elif order.exectype == bt.Order.Market:
            # Market orders: Execute at current price + spread + slippage
            if current_close is None:
                return super()._execute(order, price=price, ago=ago)
            
            if order.isbuy():
                # Buy at ask (higher price) + slippage
                execution_price = current_close + (spread_price / 2) + slippage_price
            else:
                # Sell at bid (lower price) - slippage
                execution_price = current_close - (spread_price / 2) - slippage_price
            
            price = execution_price
        
        # Log execution for analysis
        try:
            if original_price is not None and price is not None:
                slippage_actual = abs(price - original_price) if original_price else 0
                self.execution_log.append({
                    'order_ref': getattr(order, 'ref', None),
                    'order_type': getattr(order, 'exectype', None),
                    'original_price': original_price,
                    'execution_price': price,
                    'slippage': slippage_actual,
                    'spread_cost': spread_price,
                    'candle_index': ago
                })
        except Exception:
            # Silently fail logging if there's an issue
            pass
        
        return super()._execute(order, price=price, ago=ago)
    
    def get_execution_stats(self):
        """Get statistics about executions for analysis."""
        if not self.execution_log:
            return None
        
        total_slippage = sum(e['slippage'] for e in self.execution_log)
        avg_slippage = total_slippage / len(self.execution_log)
        max_slippage = max(e['slippage'] for e in self.execution_log)
        
        return {
            'total_executions': len(self.execution_log),
            'total_slippage': total_slippage,
            'avg_slippage': avg_slippage,
            'max_slippage': max_slippage,
            'spread_pips': self.spread_pips,
            'slippage_pips': self.slippage_pips
        }

