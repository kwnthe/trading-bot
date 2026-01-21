import backtrader as bt
from src.utils.strategy_utils.general_utils import convert_pips_to_price, convert_micropips_to_price

class BacktestingBroker(bt.brokers.BackBroker):
    def __init__(self, spread_pips: float = 0.0, *args, **kwargs):
        """
        Initialize BacktestingBroker with optional spread.
        
        Args:
            spread_pips: Spread in pips (default: 0.0 for no spread)
                         For forex: 1-3 pips typical
                         For metals (XAGUSD/XAUUSD): 10-50 pips typical (0.01-0.05 USD)
        """
        super().__init__(*args, **kwargs)
        self.spread_pips = spread_pips
    
    def _get_spread_price(self, symbol: str = None):
        """
        Calculate spread price based on symbol type.
        
        Note: spread_pips is in PIPS (not micropips).
        
        Spread calculation:
        - Metals (XAGUSD/XAUUSD): 1 pip = 0.001 USD
          Note: For metals, 1 pip = 1 micropip = 0.001, so convert_micropips_to_price works
        - JPY pairs (USDJPY, EURJPY, etc.): 1 pip = 0.01 JPY
          Note: convert_micropips_to_price returns 0.001 (micropips), but we need 0.01 (pips)
        - Other forex (EURUSD, GBPUSD, etc.): 1 pip = 0.0001
          Note: convert_micropips_to_price returns 0.00001 (micropips), but we need 0.0001 (pips)
        
        Examples:
        - XAGUSD with spread_pips=20: 20 * 0.001 = 0.02 USD spread
        - EURUSD with spread_pips=2: 2 * 0.0001 = 0.0002 USD spread
        - USDJPY with spread_pips=2: 2 * 0.01 = 0.02 JPY spread
        """
        if self.spread_pips <= 0:
            return 0.0
        
        # If no symbol provided, default to forex (most common case)
        if symbol is None:
            return convert_pips_to_price(self.spread_pips)  # Default to forex (1 pip = 0.0001)
        
        symbol_upper = symbol.upper()
        
        # Metals: XAGUSD, XAUUSD, etc.
        if symbol_upper.startswith("XAU") or symbol_upper.startswith("XAG"):
            # For metals, 1 pip = 0.001 USD
            # convert_micropips_to_price returns 0.001 per micropip, but for metals
            # 1 pip = 1 micropip = 0.001, so it works correctly
            return convert_micropips_to_price(self.spread_pips, symbol)
        # JPY pairs: USDJPY, EURJPY, GBPJPY, etc.
        elif symbol_upper.endswith("JPY"):
            # For JPY pairs, 1 pip = 0.01 JPY
            # convert_micropips_to_price returns 0.001 per micropip, but we need 0.01 per pip
            # So we need to multiply by 10: spread_pips * 0.01
            return self.spread_pips * 0.01
        else:
            # Standard forex pairs: EURUSD, GBPUSD, AUDUSD, etc.
            # 1 pip = 0.0001
            # convert_micropips_to_price returns 0.00001 per micropip, but we need 0.0001 per pip
            # So we use convert_pips_to_price which correctly returns 0.0001 per pip
            return convert_pips_to_price(self.spread_pips)
    
    def _submit(self, order):
        """Override submit to allow very large position sizes and check immediate execution for LIMIT orders"""
        # For testing purposes, allow any position size
        result = super()._submit(order)
        
        # Check if LIMIT order should execute immediately on current bar
        # This handles the case where order is placed when price has already passed the limit
        # This is especially important for the first order which might execute immediately
        if order.exectype == bt.Order.Limit and order.status in [order.Submitted, order.Accepted]:
            if hasattr(order, 'data') and order.data is not None and hasattr(order, 'price') and order.price is not None:
                try:
                    limit_price = float(order.price)
                    current_low = float(order.data.low[0])
                    current_high = float(order.data.high[0])
                    current_open = float(order.data.open[0])
                    
                    # For BUY LIMIT: execute if current bar's low has touched or gone below limit
                    if order.isbuy():
                        if current_open <= limit_price:
                            # Open is at or below limit - execute at Open price
                            self._execute(order, price=current_open, ago=0)
                        elif current_low <= limit_price:
                            # Low has touched or gone below limit - execute at limit price
                            self._execute(order, price=limit_price, ago=0)
                    # For SELL LIMIT: execute if current bar's high has touched or gone above limit
                    elif order.issell():
                        if current_open >= limit_price:
                            # Open is at or above limit - execute at Open price
                            self._execute(order, price=current_open, ago=0)
                        elif current_high >= limit_price:
                            # High has touched or gone above limit - execute at limit price
                            self._execute(order, price=limit_price, ago=0)
                except (IndexError, AttributeError):
                    # Data might not be available yet, that's okay
                    pass
        
        return result
    
    def _try_exec_limit(self, order, popen, phigh, plow, pcreated):
        """
        Override Backtrader's LIMIT order execution check.
        
        This method is called by Backtrader on each bar to check if pending LIMIT orders should execute.
        The default Backtrader logic may have issues with BUY LIMIT orders, so we override it to ensure
        correct execution when price touches the limit.
        
        Args:
            order: The order to check
            popen: Price at bar open
            phigh: Price at bar high
            plow: Price at bar low
            pcreated: Price when order was created
        
        For BUY LIMIT: Execute when low <= limit_price (price has touched or gone below limit)
        For SELL LIMIT: Execute when high >= limit_price (price has touched or gone above limit)
        """
        if order.exectype != bt.Order.Limit:
            # Not a LIMIT order, use parent logic
            return super()._try_exec_limit(order, popen, phigh, plow, pcreated)
        
        # Process orders that are pending (Accepted or Submitted status)
        # Note: Some orders might still be in Submitted status when first checked
        if order.status not in [order.Submitted, order.Accepted]:
            # Try parent logic first for other statuses
            return super()._try_exec_limit(order, popen, phigh, plow, pcreated)
        
        if not hasattr(order, 'price') or order.price is None:
            return False
        
        limit_price = float(order.price)
        current_open = float(popen)
        current_high = float(phigh)
        current_low = float(plow)
        
        # For BUY LIMIT orders:
        # Execute if Open is at or below limit (immediate execution at Open)
        # OR if Low during the bar is at or below limit (execution at limit)
        if order.isbuy():
            # Use <= for BUY LIMIT: execute when price touches or goes below limit
            if current_open <= limit_price:
                # Open is at or below limit - execute at Open price
                self._execute(order, price=current_open, ago=0)
                return True
            elif current_low <= limit_price:
                # Low has touched or gone below limit - execute at limit price
                self._execute(order, price=limit_price, ago=0)
                return True
        
        # For SELL LIMIT orders:
        # Execute if Open is at or above limit (immediate execution at Open)
        # OR if High during the bar is at or above limit (execution at limit)
        else:  # order.issell()
            # Use >= for SELL LIMIT: execute when price touches or goes above limit
            if current_open >= limit_price:
                # Open is at or above limit - execute at Open price
                self._execute(order, price=current_open, ago=0)
                return True
            elif current_high >= limit_price:
                # High has touched or gone above limit - execute at limit price
                self._execute(order, price=limit_price, ago=0)
                return True
        
        # Order should not execute on this bar - try parent logic as fallback
        # This ensures we don't break any edge cases Backtrader handles
        return super()._try_exec_limit(order, popen, phigh, plow, pcreated)
    
    def _process_exec(self, order):
        """
        Override Backtrader's order processing to ensure LIMIT orders execute correctly.
        
        This method is called by Backtrader during each bar to process pending orders.
        We override it to ensure BUY LIMIT orders execute when price touches the limit.
        """
        # For LIMIT orders, use our custom logic
        if order.exectype == bt.Order.Limit and order.status == order.Accepted:
            if hasattr(order, 'data') and order.data is not None and hasattr(order, 'price') and order.price is not None:
                limit_price = float(order.price)
                current_low = float(order.data.low[0])
                current_high = float(order.data.high[0])
                current_open = float(order.data.open[0])
                
                # For BUY LIMIT orders:
                if order.isbuy():
                    if current_open < limit_price:
                        # Open is below limit - execute at Open price
                        self._execute(order, price=current_open, ago=0)
                        return
                    elif current_low <= limit_price:
                        # Low has touched or gone below limit - execute at limit price
                        self._execute(order, price=limit_price, ago=0)
                        return
                
                # For SELL LIMIT orders:
                else:  # order.issell()
                    if current_open > limit_price:
                        # Open is above limit - execute at Open price
                        self._execute(order, price=current_open, ago=0)
                        return
                    elif current_high >= limit_price:
                        # High has touched or gone above limit - execute at limit price
                        self._execute(order, price=limit_price, ago=0)
                        return
        
        # For all other cases, use parent processing
        try:
            return super()._process_exec(order)
        except AttributeError:
            # If _process_exec doesn't exist, that's okay - Backtrader will handle it
            pass
    
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
        Override execution to execute orders at exact price (with optional spread).
        For backtesting, this gives execution at the order price with spread cost.
        
        Spread handling:
        - Buy orders: Execute at price + spread/2 (paying the ask)
        - Sell orders: Execute at price - spread/2 (paying the bid)
        
        Backtrader by default:
        - Stop orders execute at worst price (high for buy stops, low for sell stops)
        - Limit orders execute at best price (low for buy limits, high for sell limits)
        
        This override executes all orders at the exact order price (with spread) for consistent backtesting.
        """
        # For stop orders and limit orders, execute at the exact order price
        if order.exectype in [bt.Order.Stop, bt.Order.StopLimit, bt.Order.Limit]:
            # The order's price attribute contains the limit/stop price
            # Override the execution price to use the order price exactly
            if hasattr(order, 'price') and order.price is not None:
                price = float(order.price)
        
        # Get symbol from order data for symbol-aware spread calculation
        symbol = None
        if hasattr(order, 'data') and order.data is not None:
            if hasattr(order.data, '_name'):
                symbol = order.data._name
        
        # Calculate spread price based on symbol type
        spread_price = self._get_spread_price(symbol)
        
        # Apply spread if configured
        if spread_price > 0 and price is not None:
            if order.isbuy():
                # Buy orders pay ask (higher price) = price + spread/2
                price = price + (spread_price / 2)
            else:
                # Sell orders pay bid (lower price) = price - spread/2
                price = price - (spread_price / 2)
        
        # Call parent execution with only the arguments it accepts (order, price, ago)
        return super()._execute(order, price=price, ago=ago)
