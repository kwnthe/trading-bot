import backtrader as bt

class BacktestingBroker(bt.brokers.BackBroker):
    def _submit(self, order):
        """Override submit to allow very large position sizes"""
        # For testing purposes, allow any position size
        return super()._submit(order)
    
    def _validate_order(self, order):
        """Override validation to allow large positions"""
        # Skip size validation for testing
        return True
    
    def _check_margin(self, order):
        """Override margin check to allow large positions"""
        # Skip margin checks for testing
        return True
    
    def _check_cash(self, order):
        """Override cash check to allow large positions"""
        # Skip cash checks for testing
        return True
    
    def _execute(self, order, price=None, ago=0, **kwargs):
        """
        Override execution to execute orders at exact price (no slippage).
        For backtesting, this gives perfect execution at the order price.
        
        Backtrader by default:
        - Stop orders execute at worst price (high for buy stops, low for sell stops)
        - Limit orders execute at best price (low for buy limits, high for sell limits)
        
        This override executes all orders at the exact order price for consistent backtesting.
        """
        # For stop orders and limit orders, execute at the exact order price
        if order.exectype in [bt.Order.Stop, bt.Order.StopLimit, bt.Order.Limit]:
            # The order's price attribute contains the limit/stop price
            # Override the execution price to use the order price exactly
            if hasattr(order, 'price') and order.price is not None:
                price = float(order.price)
        
        # Call parent execution with only the arguments it accepts (order, price, ago)
        return super()._execute(order, price=price, ago=ago)
