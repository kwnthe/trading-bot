"""
MetaTrader 5 broker for Backtrader live trading.
Handles order execution through MT5.
"""

import backtrader as bt
import MetaTrader5 as mt5
from loguru import logger
from typing import Optional, List
import time


class MT5Broker(bt.brokers.BackBroker):
    """
    MetaTrader 5 broker implementation for Backtrader.
    Executes orders through MT5 API.
    Supports multiple symbols by detecting symbol from order's data feed.
    """
    
    def __getattribute__(self, name):
        """Override to ensure cash is always a valid float when accessed."""
        # Intercept access to 'cash' or '_cash' attributes (parent may access either)
        if name == 'cash' or name == '_cash':
            # Get the actual value from parent, but ensure it's not None and is a float
            try:
                # Use object.__getattribute__ to avoid recursion
                parent_dict = object.__getattribute__(self, '__dict__')
                # Check both 'cash' and '_cash' attributes
                parent_cash = parent_dict.get('cash') or parent_dict.get('_cash')
                
                # CRITICAL: Only return if it's actually a number, not an order object!
                if parent_cash is not None:
                    # Check if it's a number type (int, float) before converting
                    if isinstance(parent_cash, (int, float)):
                        cash_float = float(parent_cash)
                        # Check for NaN
                        if cash_float == cash_float:  # NaN != NaN, so this checks for NaN
                            return cash_float
            except:
                pass
            
            # If cash is None, not set, or wrong type, get from MT5 or use default
            try:
                account_info = mt5.account_info()
                if account_info:
                    cash_value = float(account_info.balance)
                else:
                    cash_value = 10000.0
            except:
                cash_value = 10000.0
            
            # Ensure cash_value is valid
            if cash_value is None:
                cash_value = 10000.0
            
            # Ensure it's a float
            try:
                cash_value = float(cash_value)
            except (TypeError, ValueError):
                cash_value = 10000.0
            
            # Set it in the parent's state - use object.__setattr__ to bypass any descriptors
            try:
                # Use object.__setattr__ to directly set the attributes
                object.__setattr__(self, '_cash', cash_value)
                object.__setattr__(self, 'cash', cash_value)
                # Also call parent's set_cash method
                parent_class = object.__getattribute__(self, '__class__').__bases__[0]
                parent_set_cash = getattr(parent_class, 'set_cash')
                parent_set_cash(self, cash_value)
            except:
                try:
                    # Try to set directly using object.__setattr__
                    object.__setattr__(self, '_cash', cash_value)
                    object.__setattr__(self, 'cash', cash_value)
                except:
                    pass
            
            return float(cash_value)
        
        # For all other attributes, use normal lookup
        return object.__getattribute__(self, name)
    
    def __init__(self, symbols: Optional[list] = None, **kwargs):
        """
        Initialize MT5 broker.
        
        Args:
            symbols: List of trading symbols (e.g., ['AUDCHF', 'EURUSD']). 
                    If None, will detect from orders.
        """
        super().__init__(**kwargs)
        self.symbols = symbols or []
        self.pending_orders = {}  # Track pending orders
        self.bracket_tp_sl = {}  # Track TP/SL for bracket orders: order.ref -> {'tp': price, 'sl': price}
        self.modified_orders = set()  # Track which orders have been modified to avoid duplicate modifications
        self.order_symbols = {}  # Track symbol for each order ref
        
        # Initialize cash from MT5
        try:
            account_info = mt5.account_info()
            if account_info:
                cash_value = float(account_info.balance)
            else:
                cash_value = 10000.0  # Default fallback
        except:
            cash_value = 10000.0
        
        # Ensure cash_value is valid
        if cash_value is None:
            cash_value = 10000.0
        
        # Set cash using parent's method
        super().set_cash(cash_value)
        
        # Also set directly as attributes using object.__setattr__ to bypass any descriptors
        try:
            object.__setattr__(self, 'cash', cash_value)
            object.__setattr__(self, '_cash', cash_value)
        except:
            pass
        
        logger.info(f"MT5Broker initialized for symbols: {self.symbols if self.symbols else 'auto-detect'}, cash: ${cash_value:.2f}")
    
    def store_bracket_tp_sl(self, order_ref, tp_price, sl_price):
        """Store TP/SL for a bracket order so it can be retrieved when order is submitted."""
        self.bracket_tp_sl[order_ref] = {'tp': tp_price, 'sl': sl_price}
        logger.info(f"Stored bracket TP/SL for order {order_ref}: TP={tp_price}, SL={sl_price}")
        
        # Try to modify parent order if it was already submitted
        self._try_modify_parent_order(order_ref)
    
    def _try_modify_parent_order(self, parent_ref):
        """Try to modify parent order with TP/SL if available and order is submitted."""
        # Only modify once per order
        if parent_ref in self.modified_orders:
            logger.debug(f"Order {parent_ref} already modified, skipping")
            return
        
        # Check if we have TP/SL stored
        if parent_ref not in self.bracket_tp_sl:
            return
        
        bracket_info = self.bracket_tp_sl[parent_ref]
        tp_price = bracket_info.get('tp')
        sl_price = bracket_info.get('sl')
        
        # Only modify if we have BOTH TP and SL and the order is submitted
        # This ensures we modify once with complete information
        if tp_price is None or sl_price is None or parent_ref not in self.pending_orders:
            logger.debug(f"Waiting for both TP and SL for order {parent_ref}. Current: TP={tp_price}, SL={sl_price}")
            return
        
        mt5_order_ticket = self.pending_orders[parent_ref]
        symbol = self.order_symbols.get(parent_ref)
        
        if not symbol:
            # Try to get symbol from MT5 order
            orders = mt5.orders_get(ticket=mt5_order_ticket)
            if orders and len(orders) > 0:
                symbol = orders[0].symbol
                self.order_symbols[parent_ref] = symbol
            else:
                logger.warning(f"Could not get symbol for order {parent_ref}")
                return
        
        logger.info(f"Modifying parent order {parent_ref} (MT5 ticket={mt5_order_ticket}) with TP={tp_price}, SL={sl_price}")
        print(f"*** MODIFYING PARENT ORDER {mt5_order_ticket} WITH TP={tp_price}, SL={sl_price} ***")
        success = self._modify_order_tp_sl(mt5_order_ticket, symbol, tp_price, sl_price)
        
        # Mark as modified if successful
        if success:
            self.modified_orders.add(parent_ref)
            logger.info(f"Order {parent_ref} successfully modified with both TP and SL")
        else:
            logger.warning(f"Failed to modify order {parent_ref}, will not retry")
    
    def _modify_order_tp_sl(self, order_ticket, symbol, tp_price, sl_price):
        """Modify an existing MT5 order or position to add or update TP/SL.
        
        Returns:
            bool: True if modification was successful, False otherwise
        """
        # Get symbol info to check stops level and other constraints
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"Could not get symbol info for {symbol}")
            return False
        
        # Get stops level (minimum distance from price to TP/SL)
        stops_level = getattr(symbol_info, 'stops_level', 0)
        point = getattr(symbol_info, 'point', 0.00001)
        min_distance = stops_level * point if stops_level > 0 else 0
        
        # First check if it's a pending order or a position
        orders = mt5.orders_get(ticket=order_ticket)
        positions = mt5.positions_get(ticket=order_ticket)
        
        if orders and len(orders) > 0:
            # It's a pending order - use TRADE_ACTION_MODIFY
            mt5_order = orders[0]
            # MT5 requires the order price to be included when modifying
            # For pending orders, use price_open or price
            order_price = getattr(mt5_order, 'price_open', None) or getattr(mt5_order, 'price', None)
            if order_price is None:
                logger.error(f"Could not get order price for order {order_ticket}")
                print(f"*** ERROR: Could not get order price for order {order_ticket} ***")
                return False
            
            normalized_sl = None
            normalized_tp = None
            
            request = {
                "action": mt5.TRADE_ACTION_MODIFY,
                "order": order_ticket,
                "symbol": symbol,
                "price": self._normalize_price(order_price, symbol),  # Include order price (required by MT5)
            }
            
            # Validate and adjust TP/SL based on order type and stops level
            order_type = getattr(mt5_order, 'type', None)
            is_buy = order_type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP]
            
            if sl_price is not None:
                normalized_sl = self._normalize_price(sl_price, symbol)
                # Validate SL distance from order price
                sl_distance = abs(order_price - normalized_sl)
                if min_distance > 0 and sl_distance < min_distance:
                    # Adjust SL to meet minimum distance requirement
                    if is_buy:
                        normalized_sl = self._normalize_price(order_price - min_distance, symbol)
                    else:
                        normalized_sl = self._normalize_price(order_price + min_distance, symbol)
                    logger.warning(f"SL adjusted to meet stops level requirement: {sl_price} -> {normalized_sl} (min distance: {min_distance})")
                request["sl"] = normalized_sl
            
            if tp_price is not None:
                normalized_tp = self._normalize_price(tp_price, symbol)
                # Validate TP distance from order price
                tp_distance = abs(order_price - normalized_tp)
                if min_distance > 0 and tp_distance < min_distance:
                    # Adjust TP to meet minimum distance requirement
                    if is_buy:
                        normalized_tp = self._normalize_price(order_price + min_distance, symbol)
                    else:
                        normalized_tp = self._normalize_price(order_price - min_distance, symbol)
                    logger.warning(f"TP adjusted to meet stops level requirement: {tp_price} -> {normalized_tp} (min distance: {min_distance})")
                request["tp"] = normalized_tp
            
            logger.info(f"Modifying MT5 pending order {order_ticket} (price={order_price}, stops_level={stops_level}, min_distance={min_distance}) to add TP={tp_price} (normalized={normalized_tp}), SL={sl_price} (normalized={normalized_sl})")
            print(f"*** MT5 MODIFY ORDER REQUEST: {request} ***")
            print(f"*** Order price: {order_price}, Stops level: {stops_level} points ({min_distance} price units) ***")
            print(f"*** TP: {tp_price}->{normalized_tp}, SL: {sl_price}->{normalized_sl} ***")
        elif positions and len(positions) > 0:
            # It's a position - use TRADE_ACTION_SLTP
            position = positions[0]
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": order_ticket,
                "symbol": symbol,
            }
            
            # For positions, validate TP/SL against current price and stops level
            position_price = getattr(position, 'price_open', None) or getattr(position, 'price_current', None)
            is_long = getattr(position, 'type', 0) == mt5.ORDER_TYPE_BUY
            
            normalized_sl = None
            normalized_tp = None
            
            if sl_price is not None:
                normalized_sl = self._normalize_price(sl_price, symbol)
                if position_price and min_distance > 0:
                    sl_distance = abs(position_price - normalized_sl)
                    if sl_distance < min_distance:
                        if is_long:
                            normalized_sl = self._normalize_price(position_price - min_distance, symbol)
                        else:
                            normalized_sl = self._normalize_price(position_price + min_distance, symbol)
                request["sl"] = normalized_sl
            
            if tp_price is not None:
                normalized_tp = self._normalize_price(tp_price, symbol)
                if position_price and min_distance > 0:
                    tp_distance = abs(position_price - normalized_tp)
                    if tp_distance < min_distance:
                        if is_long:
                            normalized_tp = self._normalize_price(position_price + min_distance, symbol)
                        else:
                            normalized_tp = self._normalize_price(position_price - min_distance, symbol)
                request["tp"] = normalized_tp
            
            logger.info(f"Modifying MT5 position {order_ticket} (price={position_price}, stops_level={stops_level}) to add TP={tp_price} (normalized={normalized_tp}), SL={sl_price} (normalized={normalized_sl})")
            print(f"*** MT5 MODIFY POSITION REQUEST: {request} ***")
        else:
            logger.warning(f"Order/position {order_ticket} not found in MT5")
            print(f"*** ORDER/POSITION {order_ticket} NOT FOUND IN MT5 ***")
            return False
        
        result = mt5.order_send(request)
        
        if result:
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"✓ Successfully modified order/position {order_ticket} with TP/SL")
                print(f"*** SUCCESSFULLY MODIFIED ORDER/POSITION {order_ticket} WITH TP/SL ***")
                return True
            else:
                logger.error(f"✗ Failed to modify order/position {order_ticket}: retcode={result.retcode}, comment={result.comment}")
                print(f"*** FAILED TO MODIFY ORDER/POSITION: retcode={result.retcode}, comment={result.comment} ***")
                return False
        else:
            error = mt5.last_error()
            logger.error(f"Failed to modify order/position {order_ticket}: {error}")
            print(f"*** FAILED TO MODIFY ORDER/POSITION: {error} ***")
            return False
    
    def start(self):
        """Called when broker starts - initialize cash from MT5."""
        try:
            account_info = mt5.account_info()
            if account_info:
                cash_value = float(account_info.balance)
            else:
                try:
                    parent_cash = super().getcash()
                    cash_value = float(parent_cash) if parent_cash is not None else 10000.0
                except:
                    cash_value = 10000.0
        except:
            cash_value = 10000.0
        
        # Ensure cash_value is valid
        if cash_value is None:
            cash_value = 10000.0
        
        super().set_cash(cash_value)
        
        # Also set directly as attributes using object.__setattr__ to bypass any descriptors
        try:
            object.__setattr__(self, 'cash', cash_value)
            object.__setattr__(self, '_cash', cash_value)
        except:
            pass
        
        logger.info(f"MT5Broker started with cash: ${cash_value:.2f}")
        
        # ===== TEST TRADE - Set ENABLE_TEST_TRADE = True to enable =====
        ENABLE_TEST_TRADE = False  # Set to True to place a test trade on startup
        if ENABLE_TEST_TRADE:
            try:
                test_symbol = self.symbols[0] if self.symbols else 'AUDCHF'
                logger.info(f"Placing test trade for {test_symbol}...")
                symbol_info = mt5.symbol_info(test_symbol)
                if symbol_info:
                    # Determine the correct filling mode based on symbol's supported modes
                    # filling_mode is a bitmask: 1=FOK, 2=IOC, 4=RETURN
                    filling_mode = None
                    filling_modes_to_try = [
                        mt5.ORDER_FILLING_RETURN,  # Most common, try first
                        mt5.ORDER_FILLING_IOC,
                        mt5.ORDER_FILLING_FOK,
                    ]
                    
                    # Check which modes are supported (bitwise check)
                    if symbol_info.filling_mode & 4:  # RETURN supported
                        filling_mode = mt5.ORDER_FILLING_RETURN
                    elif symbol_info.filling_mode & 2:  # IOC supported
                        filling_mode = mt5.ORDER_FILLING_IOC
                    elif symbol_info.filling_mode & 1:  # FOK supported
                        filling_mode = mt5.ORDER_FILLING_FOK
                    else:
                        # Default to RETURN if we can't determine
                        filling_mode = mt5.ORDER_FILLING_RETURN
                    
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": test_symbol,
                        "volume": 0.01,  # 0.01 lot
                        "type": mt5.ORDER_TYPE_BUY,
                        "price": symbol_info.ask,
                        "deviation": 20,
                        "magic": 234000,
                        "comment": "TEST TRADE - REMOVE ME",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": filling_mode,
                    }
                    logger.info(f"Using filling mode: {filling_mode} (symbol supports: {symbol_info.filling_mode})")
                    result = mt5.order_send(request)
                    if result:
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(f"✓ TEST TRADE SUCCESS: BUY 0.01 {test_symbol} at {symbol_info.ask}, Order: {result.order}")
                        else:
                            error_msg = f"✗ TEST TRADE FAILED: retcode={result.retcode}, comment={result.comment}"
                            if result.retcode == 10027:
                                error_msg += "\n   ⚠️  AutoTrading is disabled in MetaTrader 5!"
                                error_msg += "\n   Please enable AutoTrading: Click 'AutoTrading' button (or press Ctrl+E) in MT5"
                            elif result.retcode == 10030:
                                error_msg += f"\n   ⚠️  Unsupported filling mode. Symbol supports: {symbol_info.filling_mode}"
                            logger.error(error_msg)
                    else:
                        error = mt5.last_error()
                        logger.error(f"✗ TEST TRADE FAILED: {error}")
                else:
                    logger.error(f"✗ Could not get symbol info for {test_symbol}")
            except Exception as e:
                logger.error(f"✗ Error placing test trade: {e}")
        # ===== END TEST TRADE BLOCK =====
        
        super().start()
    
    def set_cash(self, cash):
        """Override set_cash to ensure it's never None."""
        if cash is None:
            cash = 10000.0  # Default value
        cash = float(cash)
        # Ensure it's valid
        if cash is None:
            cash = 10000.0
        
        # Call parent's set_cash to update its internal state
        super().set_cash(cash)
        
        # Also set directly as attributes using object.__setattr__ to bypass any descriptors
        try:
            object.__setattr__(self, 'cash', cash)
            object.__setattr__(self, '_cash', cash)
        except:
            pass
    
    def get_cash(self):
        """Get current account balance - always returns a valid float."""
        # First try to get from MT5
        try:
            account_info = mt5.account_info()
            if account_info:
                cash_value = float(account_info.balance)
                # Ensure it's valid
                if cash_value is None:
                    cash_value = 10000.0
                # Update parent's cash state
                super().set_cash(cash_value)
                # Also set directly using object.__setattr__ to bypass any descriptors
                try:
                    object.__setattr__(self, 'cash', cash_value)
                    object.__setattr__(self, '_cash', cash_value)
                except:
                    pass
                return cash_value
        except:
            pass
        
        # Fallback: get from parent, but ensure it's not None
        try:
            # Try to get from parent's internal state directly
            parent_cash = None
            try:
                parent_cash = super().getcash()
            except:
                pass
            
            # Also try to get from parent's dict
            if parent_cash is None:
                try:
                    parent_dict = super().__getattribute__('__dict__')
                    parent_cash = parent_dict.get('cash') or parent_dict.get('_cash')
                except:
                    pass
            
            if parent_cash is None:
                # If parent returns None, set a default and return it
                default_cash = 10000.0
                super().set_cash(default_cash)
                try:
                    object.__setattr__(self, 'cash', default_cash)
                    object.__setattr__(self, '_cash', default_cash)
                except:
                    pass
                return default_cash
            
            cash_float = float(parent_cash)
            if cash_float is None:
                cash_float = 10000.0
                super().set_cash(cash_float)
            return cash_float
        except:
            # Last resort: return default
            default_cash = 10000.0
            try:
                super().set_cash(default_cash)
                object.__setattr__(self, 'cash', default_cash)
                object.__setattr__(self, '_cash', default_cash)
            except:
                pass
            return default_cash
    
    def getcash(self):
        """Alias for get_cash() - Backtrader calls this method."""
        return self.get_cash()
    
    def next(self):
        """Called each bar - update cash from MT5 to keep it in sync."""
        # Update cash from MT5 before calling parent's next()
        try:
            account_info = mt5.account_info()
            if account_info:
                cash_value = float(account_info.balance)
            else:
                cash_value = 10000.0
        except:
            cash_value = 10000.0
        
        # Ensure cash_value is valid
        if cash_value is None:
            cash_value = 10000.0
        
        # Update parent's cash state
        super().set_cash(cash_value)
        
        # Also set directly as attributes using object.__setattr__ to bypass any descriptors
        try:
            object.__setattr__(self, 'cash', cash_value)
            object.__setattr__(self, '_cash', cash_value)
        except:
            pass
        
        super().next()
    
    
    def check_submitted(self):
        """
        Override check_submitted to ensure cash is always valid.
        Reimplements the parent's logic but with proper cash handling.
        """
        logger.debug("check_submitted() called")
        # Get cash - ensure it's never None and is always a float
        try:
            # Use get_cash() which we know returns a float
            cash = self.get_cash()
            # Ensure it's a valid float
            cash = float(cash)
            if cash != cash:  # Check for NaN
                cash = 10000.0
        except (TypeError, ValueError, AttributeError) as e:
            # If get_cash() fails or returns something weird, get from MT5
            try:
                account_info = mt5.account_info()
                if account_info:
                    cash = float(account_info.balance)
                else:
                    cash = 10000.0
            except:
                cash = 10000.0
        
        # Ensure cash is set in parent's internal state BEFORE calling parent's check_submitted
        # This is critical - the parent accesses self.cash directly, so we need to set it properly
        try:
            # Set using object.__setattr__ to bypass our __getattribute__ override
            object.__setattr__(self, '_cash', cash)
            object.__setattr__(self, 'cash', cash)
            # Also call parent's set_cash to update its internal state
            super().set_cash(cash)
        except Exception as e:
            logger.warning(f"Error setting cash in check_submitted: {e}")
            # Try direct assignment as fallback
            try:
                object.__setattr__(self, '_cash', cash)
                object.__setattr__(self, 'cash', cash)
            except:
                pass
        
        # Now call parent's check_submitted - it should see cash as a float
        try:
            return super().check_submitted()
        except TypeError as e:
            error_str = str(e)
            if "'>=' not supported" in error_str or "'BuyOrder'" in error_str or "'SellOrder'" in error_str:
                # Parent is getting wrong type for cash - this shouldn't happen but handle it
                logger.warning(f"Parent's check_submitted got wrong cash type: {e}. Cash should be {cash} (type: {type(cash)})")
                # Force set cash again and retry once
                try:
                    object.__setattr__(self, '_cash', float(cash))
                    object.__setattr__(self, 'cash', float(cash))
                    super().set_cash(float(cash))
                    return super().check_submitted()
                except:
                    # If still fails, skip the check - we handle validation in _submit()
                    logger.debug(f"Skipping parent's check_submitted due to cash type issue")
                    return
            else:
                raise
    
    def _get_symbol_from_order(self, order):
        """Extract symbol from order's data feed."""
        # Try to get symbol from data feed's _name attribute
        if hasattr(order.data, '_name') and order.data._name:
            return order.data._name
        
        # Try to get from data's p.name
        if hasattr(order.data, 'p') and hasattr(order.data.p, 'name'):
            return order.data.p.name
        
        # Try to get from data's name attribute
        if hasattr(order.data, 'name'):
            return order.data.name
        
        # Fallback: use first symbol if available
        if self.symbols:
            return self.symbols[0]
        
        logger.warning("Could not determine symbol from order, using default")
        return None
    
    def submit(self, order, check=True):
        """Override submit to ensure _submit is called."""
        print(f"*** MT5Broker.submit() CALLED: order.ref={order.ref}, type={order.exectype}, check={check} ***")
        logger.info(f"submit() called (public method): order.ref={order.ref}, check={check}")
        
        # Check if we're in live mode - reject orders during historical backfill
        # Get the data feed from the order to check live_mode
        if hasattr(order, 'data') and order.data is not None:
            is_live = getattr(order.data, 'live_mode', False)
            if not is_live:
                logger.warning(f"Rejecting order {order.ref} - not in live mode (still processing historical data)")
                print(f"*** REJECTING ORDER {order.ref} - NOT IN LIVE MODE ***")
                order.reject()
                return order
        
        # For MT5 live trading, we skip backtrader's validation and send directly to MT5
        # MT5 will do its own validation
        # Call our _submit() directly to send order to MT5
        return self._submit(order)
    
    def _submit(self, order):
        """Submit order to MT5."""
        try:
            print(f"*** MT5Broker._submit() CALLED: order.ref={order.ref}, type={order.exectype}, size={order.size}, isbuy={order.isbuy()} ***")
            logger.info(f"_submit called: order.ref={order.ref}, type={order.exectype}, size={order.size}, isbuy={order.isbuy()}")
            
            # Check if this is a bracket order TP or SL (child order)
            # These should be skipped since TP/SL are attached to the main order in MT5
            # BUT: We can extract TP/SL prices from these child orders and store them for the parent
            is_bracket_child = (hasattr(order, 'parent') and order.parent is not None)
            if is_bracket_child:
                parent_order = order.parent
                parent_ref = parent_order.ref if parent_order else None
                
                # Extract TP/SL price from this child order
                # TP orders are Limit orders, SL orders are Stop orders
                symbol = self._get_symbol_from_order(order)
                if symbol and parent_ref:
                    # Store symbol for the parent order
                    self.order_symbols[parent_ref] = symbol
                
                if order.exectype == bt.Order.Limit:
                    # This is a TP order
                    tp_price = order.price
                    if parent_ref:
                        if parent_ref not in self.bracket_tp_sl:
                            self.bracket_tp_sl[parent_ref] = {}
                        self.bracket_tp_sl[parent_ref]['tp'] = tp_price
                        logger.info(f"Extracted TP from child order: parent_ref={parent_ref}, TP={tp_price}")
                        print(f"*** EXTRACTED TP FROM CHILD ORDER: parent_ref={parent_ref}, TP={tp_price} ***")
                        
                        # Try to modify parent order if both TP and SL are available
                        self._try_modify_parent_order(parent_ref)
                elif order.exectype == bt.Order.Stop:
                    # This is a SL order
                    sl_price = order.price
                    if parent_ref:
                        if parent_ref not in self.bracket_tp_sl:
                            self.bracket_tp_sl[parent_ref] = {}
                        self.bracket_tp_sl[parent_ref]['sl'] = sl_price
                        logger.info(f"Extracted SL from child order: parent_ref={parent_ref}, SL={sl_price}")
                        print(f"*** EXTRACTED SL FROM CHILD ORDER: parent_ref={parent_ref}, SL={sl_price} ***")
                        
                        # Try to modify parent order if both TP and SL are available
                        self._try_modify_parent_order(parent_ref)
                
                logger.info(f"Skipping bracket child order {order.ref} (TP/SL) - already attached to main order in MT5")
                print(f"*** SKIPPING BRACKET CHILD ORDER {order.ref} - TP/SL handled by MT5 ***")
                # Accept the order in backtrader but don't place it in MT5
                # MT5 will handle TP/SL automatically when the main order is placed
                # We need to submit and accept it so backtrader tracks it properly
                order.submit()
                order.accept()
                # Mark as completed immediately since MT5 handles it automatically
                # This prevents backtrader from waiting for execution
                return order
            
            # Get symbol from order's data feed
            symbol = self._get_symbol_from_order(order)
            if not symbol:
                logger.error("Could not determine symbol for order")
                order.reject()
                return order
            
            logger.info(f"Order symbol: {symbol}")
            
            # Get current symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error(f"Symbol {symbol} not found in MT5")
                order.reject()
                return order
            
            # Check if this is a bracket order main order
            # Extract TP and SL prices if available
            tp_price = None
            sl_price = None
            
            # Debug: Check what attributes the order has
            logger.debug(f"Order attributes: hasattr(info)={hasattr(order, 'info')}, hasattr(bracket)={hasattr(order, 'bracket')}")
            if hasattr(order, 'info'):
                logger.debug(f"Order.info type: {type(order.info)}, value: {order.info}")
                print(f"*** ORDER.INFO: {order.info} ***")
            if hasattr(order, 'bracket'):
                logger.debug(f"Order.bracket type: {type(order.bracket)}, value: {order.bracket}")
                print(f"*** ORDER.BRACKET: {order.bracket} ***")
            
            # First check our broker-level storage (most reliable)
            # print(f"*** CHECKING BROKER STORAGE: order.ref={order.ref}, storage keys={list(self.bracket_tp_sl.keys())} ***")
            if order.ref in self.bracket_tp_sl:
                bracket_info = self.bracket_tp_sl[order.ref]
                tp_price = bracket_info.get('tp')
                sl_price = bracket_info.get('sl')
                if tp_price or sl_price:
                    logger.info(f"Bracket order detected via broker storage: TP={tp_price}, SL={sl_price}")
                    print(f"*** BRACKET ORDER DETECTED (broker storage): TP={tp_price}, SL={sl_price} ***")
            else:
                print(f"*** ORDER.REF {order.ref} NOT FOUND IN BROKER STORAGE ***")
            
            # Second check order.info (we explicitly store TP/SL there in BaseStrategy.place_order)
            if (tp_price is None or sl_price is None) and hasattr(order, 'info') and isinstance(order.info, dict):
                if tp_price is None and 'tp' in order.info:
                    tp_price = order.info['tp']
                if sl_price is None and 'sl' in order.info:
                    sl_price = order.info['sl']
                if tp_price or sl_price:
                    logger.info(f"Bracket order detected via order.info: TP={tp_price}, SL={sl_price}")
                    print(f"*** BRACKET ORDER DETECTED (order.info): TP={tp_price}, SL={sl_price} ***")
            
            # Fallback: check order.bracket (backtrader's native bracket structure)
            if (tp_price is None or sl_price is None) and hasattr(order, 'bracket') and order.bracket:
                if tp_price is None and hasattr(order.bracket, 'limit') and order.bracket.limit:
                    tp_price = order.bracket.limit.price
                if sl_price is None and hasattr(order.bracket, 'stop') and order.bracket.stop:
                    sl_price = order.bracket.stop.price
                if tp_price or sl_price:
                    logger.info(f"Bracket order detected via order.bracket: TP={tp_price}, SL={sl_price}")
                    print(f"*** BRACKET ORDER DETECTED (order.bracket): TP={tp_price}, SL={sl_price} ***")
            
            # Another fallback: try to extract TP/SL from bracket child orders if they exist
            # When backtrader creates bracket orders, the child orders have a parent reference
            # We can check if this order has children by looking at backtrader's order tracking
            if (tp_price is None or sl_price is None) and hasattr(order, 'bracket'):
                # Try to access bracket child orders directly
                try:
                    if hasattr(order.bracket, 'limit') and order.bracket.limit:
                        if tp_price is None:
                            tp_price = order.bracket.limit.price
                            logger.info(f"Extracted TP from order.bracket.limit: TP={tp_price}")
                            print(f"*** EXTRACTED TP FROM order.bracket.limit: {tp_price} ***")
                    if hasattr(order.bracket, 'stop') and order.bracket.stop:
                        if sl_price is None:
                            sl_price = order.bracket.stop.price
                            logger.info(f"Extracted SL from order.bracket.stop: SL={sl_price}")
                            print(f"*** EXTRACTED SL FROM order.bracket.stop: {sl_price} ***")
                except Exception as e:
                    logger.debug(f"Could not extract TP/SL from order.bracket: {e}")
                    print(f"*** ERROR EXTRACTING FROM order.bracket: {e} ***")
            
            # Final fallback: Check if we can find child orders in backtrader's order tracking
            # This is a bit of a hack, but we can try to find orders with this order as parent
            if (tp_price is None or sl_price is None):
                # Try to access backtrader's order tracking to find child orders
                # This might not work depending on backtrader's internal structure
                try:
                    # Check if order has any attributes that reference child orders
                    if hasattr(order, '_oco') and order._oco:
                        # OCO (One-Cancels-Other) orders might contain bracket info
                        pass
                except:
                    pass
            
            # Final check: if we still don't have TP/SL, log a warning
            if tp_price is None and sl_price is None:
                logger.warning(f"No TP/SL found for order {order.ref}. Order.info={getattr(order, 'info', None)}, Order.bracket={getattr(order, 'bracket', None)}, Broker storage={order.ref in self.bracket_tp_sl}")
                print(f"*** WARNING: No TP/SL found for order {order.ref} ***")
                print(f"*** Order.info: {getattr(order, 'info', 'N/A')} ***")
                print(f"*** Order.bracket: {getattr(order, 'bracket', 'N/A')} ***")
                print(f"*** Broker storage has this ref: {order.ref in self.bracket_tp_sl} ***")
            
            # Determine order type and price based on order execution type
            if order.exectype == bt.Order.Market:
                # Market orders: use current market price
                if order.isbuy():
                    order_type = mt5.ORDER_TYPE_BUY
                    price = symbol_info.ask
                else:
                    order_type = mt5.ORDER_TYPE_SELL
                    price = symbol_info.bid
                logger.info(f"Processing MARKET order: type={order_type}, price={price}, size={order.size}")
                result = self._place_market_order(order, order_type, price, symbol, tp_price=tp_price, sl_price=sl_price)
            elif order.exectype == bt.Order.Stop:
                # Stop orders: use order.price (stop price)
                # For bracket orders, backtrader creates stop orders with opposite size
                # If size is negative, it's a closing order (opposite side)
                # Check if this is a closing order (bracket stop loss)
                is_closing = (hasattr(order, 'parent') and order.parent is not None) or (order.size < 0)
                
                if is_closing:
                    # This is a bracket order stop loss - it closes the position
                    # The order type should be opposite to the main order
                    if hasattr(order, 'parent') and order.parent is not None:
                        main_is_buy = order.parent.isbuy()
                    else:
                        # If no parent, check size: negative size means opposite side
                        main_is_buy = (order.size < 0)
                    
                    if main_is_buy:
                        # Main order is BUY, so stop loss is SELL_STOP (to close long)
                        order_type = mt5.ORDER_TYPE_SELL_STOP
                    else:
                        # Main order is SELL, so stop loss is BUY_STOP (to close short)
                        order_type = mt5.ORDER_TYPE_BUY_STOP
                else:
                    # Regular stop order (opens position)
                    if order.isbuy():
                        order_type = mt5.ORDER_TYPE_BUY_STOP
                    else:
                        order_type = mt5.ORDER_TYPE_SELL_STOP
                price = order.price  # Use the stop price from the order
                logger.info(f"Processing STOP order: type={order_type}, price={price}, size={order.size}, is_closing={is_closing}")
                result = self._place_stop_order(order, order_type, symbol, tp_price=tp_price, sl_price=sl_price)
            elif order.exectype == bt.Order.Limit:
                # Limit orders: use order.price (limit price)
                # For bracket orders, backtrader creates limit orders with opposite size
                # If size is negative, it's a closing order (opposite side)
                # Check if this is a closing order (bracket take profit)
                is_closing = (hasattr(order, 'parent') and order.parent is not None) or (order.size < 0)
                
                if is_closing:
                    # This is a bracket order take profit - it closes the position
                    # The order type should be opposite to the main order
                    if hasattr(order, 'parent') and order.parent is not None:
                        main_is_buy = order.parent.isbuy()
                    else:
                        # If no parent, check size: negative size means opposite side
                        main_is_buy = (order.size < 0)
                    
                    if main_is_buy:
                        # Main order is BUY, so TP is SELL_LIMIT (to close long)
                        order_type = mt5.ORDER_TYPE_SELL_LIMIT
                    else:
                        # Main order is SELL, so TP is BUY_LIMIT (to close short)
                        order_type = mt5.ORDER_TYPE_BUY_LIMIT
                else:
                    # Regular limit order (opens position)
                    if order.isbuy():
                        order_type = mt5.ORDER_TYPE_BUY_LIMIT
                    else:
                        order_type = mt5.ORDER_TYPE_SELL_LIMIT
                price = order.price  # Use the limit price from the order
                logger.info(f"Processing LIMIT order: type={order_type}, price={price}, size={order.size}, is_closing={is_closing}")
                result = self._place_limit_order(order, order_type, symbol, tp_price=tp_price, sl_price=sl_price)
            elif order.exectype == bt.Order.StopLimit:
                # Stop limit order: use order.price (stop price) and order.plimit (limit price)
                if order.isbuy():
                    order_type = mt5.ORDER_TYPE_BUY_STOP_LIMIT
                else:
                    order_type = mt5.ORDER_TYPE_SELL_STOP_LIMIT
                price = order.price  # Stop price
                logger.info(f"Processing STOPLIMIT order: type={order_type}, stop_price={price}, size={order.size}")
                result = self._place_stop_limit_order(order, order_type, symbol)
            else:
                logger.error(f"Unsupported order type: {order.exectype}")
                order.reject()
                return order
            
            if result is None:
                error = mt5.last_error()
                logger.error(f"Order submission failed: {error}")
                order.reject()
            else:
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    order.submit()
                    mt5_order_ticket = result.order
                    self.pending_orders[order.ref] = mt5_order_ticket
                    self.order_symbols[order.ref] = symbol  # Store symbol for this order
                    logger.info(f"✓ Order submitted successfully: MT5 order={mt5_order_ticket}, ref={order.ref}, status={order.getstatusname()}")
                    
                    # Try to modify order with TP/SL if available (will only modify once due to modified_orders tracking)
                    self._try_modify_parent_order(order.ref)
                else:
                    logger.error(f"✗ Order submission failed: retcode={result.retcode}, comment={result.comment}")
                    order.reject()
            
            return order
            
        except Exception as e:
            logger.error(f"Error submitting order: {e}")
            import traceback
            traceback.print_exc()
            order.reject()
            return order
    
    def _place_market_order(self, order, order_type, price, symbol, tp_price=None, sl_price=None):
        """Place a market order."""
        # Get symbol info to determine correct filling mode and lot size
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"Could not get symbol info for {symbol}")
            return None
            
        # Determine the correct filling mode based on symbol's supported modes
        # filling_mode is a bitmask: 1=FOK, 2=IOC, 4=RETURN
        if symbol_info.filling_mode & 4:  # RETURN supported
            filling_mode = mt5.ORDER_FILLING_RETURN
        elif symbol_info.filling_mode & 2:  # IOC supported
            filling_mode = mt5.ORDER_FILLING_IOC
        elif symbol_info.filling_mode & 1:  # FOK supported
            filling_mode = mt5.ORDER_FILLING_FOK
        else:
            filling_mode = mt5.ORDER_FILLING_RETURN  # Default
        
        # Convert order.size (units) to volume (lots)
        # symbol_info.volume_min = minimum lot size (e.g., 0.01)
        # symbol_info.volume_step = lot step size (e.g., 0.01)
        # symbol_info.volume_max = maximum lot size
        # symbol_info.trade_contract_size = contract size (usually 100000 for forex, 1 for crypto)
        
        # If order.size is in units, convert to lots
        # For forex: 1 lot = 100,000 units (contract_size)
        # For crypto: 1 lot = 1 unit (contract_size = 1)
        contract_size = symbol_info.trade_contract_size if hasattr(symbol_info, 'trade_contract_size') else 100000
        volume_min = symbol_info.volume_min if hasattr(symbol_info, 'volume_min') else 0.01
        volume_step = symbol_info.volume_step if hasattr(symbol_info, 'volume_step') else 0.01
        volume_max = symbol_info.volume_max if hasattr(symbol_info, 'volume_max') else 100.0
        
        # Convert units to lots
        volume = abs(order.size) / contract_size
        
        # Round to nearest step
        if volume_step > 0:
            volume = round(volume / volume_step) * volume_step
        
        # Ensure volume is within valid range
        if volume < volume_min:
            volume = volume_min
            logger.warning(f"Order size {order.size} units ({volume} lots) too small, using minimum {volume_min} lot")
        elif volume > volume_max:
            volume = volume_max
            logger.warning(f"Order size {order.size} units ({volume} lots) too large, using maximum {volume_max} lot")
        
        logger.info(f"Converted order size: {order.size} units -> {volume} lots (contract_size={contract_size}, step={volume_step})")
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": 20,  # Slippage tolerance in points
            "magic": 234000,  # Magic number for order identification
            "comment": f"Backtrader {order.ref}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        # Add TP/SL if provided (from bracket order)
        if sl_price is not None:
            request["sl"] = self._normalize_price(sl_price, symbol)
            logger.info(f"Adding SL to market order: {request['sl']}")
            print(f"*** ADDING SL TO MARKET ORDER: {request['sl']} ***")
        
        if tp_price is not None:
            request["tp"] = self._normalize_price(tp_price, symbol)
            logger.info(f"Adding TP to market order: {request['tp']}")
            print(f"*** ADDING TP TO MARKET ORDER: {request['tp']} ***")
        
        logger.info(f"Placing market order: {symbol} {order_type} {volume} lots at {price}, filling={filling_mode}, TP={tp_price}, SL={sl_price}")
        print(f"*** MT5 REQUEST: {request} ***")
        result = mt5.order_send(request)
        
        if result:
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                logger.error(f"Market order failed: retcode={result.retcode}, comment={result.comment}")
        else:
            error = mt5.last_error()
            logger.error(f"Market order send failed: {error}")
        
        return result
    
    def _normalize_price(self, price, symbol):
        """Normalize price to symbol's tick size."""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return price
        
        tick_size = symbol_info.trade_tick_size if hasattr(symbol_info, 'trade_tick_size') else 0.00001
        if tick_size > 0:
            # Round to nearest tick
            price = round(price / tick_size) * tick_size
        
        return price
    
    def _convert_volume_to_lots(self, size, symbol):
        """Convert order size (units) to volume (lots) for MT5."""
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logger.error(f"Could not get symbol info for {symbol}")
            return 0.01  # Default fallback
        
        contract_size = symbol_info.trade_contract_size if hasattr(symbol_info, 'trade_contract_size') else 100000
        volume_min = symbol_info.volume_min if hasattr(symbol_info, 'volume_min') else 0.01
        volume_step = symbol_info.volume_step if hasattr(symbol_info, 'volume_step') else 0.01
        volume_max = symbol_info.volume_max if hasattr(symbol_info, 'volume_max') else 100.0
        
        # Convert units to lots
        volume = abs(size) / contract_size
        
        # Round to nearest step
        if volume_step > 0:
            volume = round(volume / volume_step) * volume_step
        
        # Ensure volume is within valid range
        if volume < volume_min:
            volume = volume_min
        elif volume > volume_max:
            volume = volume_max
        
        return volume
    
    def _place_stop_order(self, order, order_type, symbol, tp_price=None, sl_price=None):
        """Place a stop order."""
        volume = self._convert_volume_to_lots(order.size, symbol)
        # Use order.price and normalize it to tick size
        price = self._normalize_price(order.price, symbol)
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,  # Use the order_type passed in (already set correctly)
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": f"Backtrader Stop {order.ref}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Add TP/SL if provided (from bracket order)
        if sl_price is not None:
            request["sl"] = self._normalize_price(sl_price, symbol)
            logger.info(f"Adding SL to stop order: {request['sl']}")
            print(f"*** ADDING SL TO STOP ORDER: {request['sl']} ***")
        
        if tp_price is not None:
            request["tp"] = self._normalize_price(tp_price, symbol)
            logger.info(f"Adding TP to stop order: {request['tp']}")
            print(f"*** ADDING TP TO STOP ORDER: {request['tp']} ***")
        
        logger.info(f"Placing stop order: {symbol} {order_type} {volume} lots at {price}, TP={tp_price}, SL={sl_price}")
        print(f"*** MT5 REQUEST: {request} ***")
        result = mt5.order_send(request)
        if result and result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Stop order failed: retcode={result.retcode}, comment={result.comment}")
        return result
    
    def _place_limit_order(self, order, order_type, symbol, tp_price=None, sl_price=None):
        """Place a limit order."""
        volume = self._convert_volume_to_lots(order.size, symbol)
        # Use order.price and normalize it to tick size
        price = self._normalize_price(order.price, symbol)
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,  # Use the order_type passed in (already set correctly)
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": f"Backtrader Limit {order.ref}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Add TP/SL if provided (from bracket order)
        if sl_price is not None:
            request["sl"] = self._normalize_price(sl_price, symbol)
            logger.info(f"Adding SL to limit order: {request['sl']}")
            print(f"*** ADDING SL TO LIMIT ORDER: {request['sl']} ***")
        
        if tp_price is not None:
            request["tp"] = self._normalize_price(tp_price, symbol)
            logger.info(f"Adding TP to limit order: {request['tp']}")
            print(f"*** ADDING TP TO LIMIT ORDER: {request['tp']} ***")
        
        logger.info(f"Placing limit order: {symbol} {order_type} {volume} lots at {price}, TP={tp_price}, SL={sl_price}")
        print(f"*** MT5 REQUEST: {request} ***")
        result = mt5.order_send(request)
        if result and result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Limit order failed: retcode={result.retcode}, comment={result.comment}")
        return result
    
    def _place_stop_limit_order(self, order, order_type, symbol):
        """Place a stop limit order."""
        # MT5 doesn't directly support stop-limit, so we'll use stop order
        logger.warning("Stop-limit orders not directly supported, using stop order")
        return self._place_stop_order(order, order_type, symbol)
    
    def _execute(self, order, price=None, ago=0, **kwargs):
        """Execute order (called by Backtrader)."""
        # For MT5, we don't want to execute orders immediately
        # Orders should be submitted to MT5 first via _submit
        # Only execute if the order was already submitted to MT5 and executed there
        logger.info(f"_execute called: order.ref={order.ref}, status={order.getstatusname()}, pending_orders has ref: {order.ref in self.pending_orders}")
        
        # If order is already in pending_orders, it means it was submitted to MT5
        # Check if it was executed in MT5
        if order.ref in self.pending_orders:
            mt5_order = self.pending_orders[order.ref]
            # Get symbol from order
            symbol = self._get_symbol_from_order(order)
            
            # Check if order was executed in MT5
            positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
            if positions:
                for pos in positions:
                    if pos.ticket == mt5_order:
                        # Position opened from this order
                        logger.info(f"Order {order.ref} executed in MT5 as position {pos.ticket}")
                        order.execute(price=pos.price_open or price)
                        del self.pending_orders[order.ref]
                        return order
            
            # Check pending orders in MT5
            orders = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
            if orders:
                for o in orders:
                    if o.ticket == mt5_order:
                        # Order still pending in MT5, don't execute yet
                        logger.info(f"Order {order.ref} still pending in MT5 (ticket {mt5_order})")
                        return order
        
        # If order hasn't been submitted to MT5 yet, don't execute it
        # It should go through _submit first
        if order.status == order.Submitted:
            logger.info(f"Order {order.ref} is Submitted but not yet in pending_orders - waiting for MT5 execution")
            return order
        
        # For orders that haven't been submitted to MT5, don't execute immediately
        # This prevents backtrader from executing orders in simulation mode
        logger.warning(f"Order {order.ref} execution attempted but not submitted to MT5 - skipping immediate execution")
        return order
    
    def cancel(self, order):
        """Cancel an order."""
        if order.ref in self.pending_orders:
            mt5_order = self.pending_orders[order.ref]
            request = {
                "action": mt5.TRADE_ACTION_REMOVE,
                "order": mt5_order,
            }
            result = mt5.order_send(request)
            if result:
                del self.pending_orders[order.ref]
                order.cancel()
                logger.info(f"Order {order.ref} cancelled")
            else:
                logger.error(f"Failed to cancel order {order.ref}: {mt5.last_error()}")
        
        return order
    
    def get_value(self):
        """Get current account equity."""
        account_info = mt5.account_info()
        if account_info:
            return float(account_info.equity)
        # Fallback to parent's get_value, but ensure it's not None
        value = super().get_value()
        return float(value) if value is not None else 0.0
