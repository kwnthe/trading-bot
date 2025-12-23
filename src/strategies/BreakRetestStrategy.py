import backtrader as bt
import numpy as np
from src.models.trend import Trend
from src.strategies.BaseStrategy import BaseStrategy
from src.models.order import OrderType, TradeState, OrderSide, log_trade
from src.utils.strategy_utils.general_utils import convert_micropips_to_price
from utils.logging import format_price
from utils.config import Config
import uuid
from infrastructure import LogLevel, RepositoryName
from src.utils.environment_variables import EnvironmentVariables

class BreakRetestStrategy(BaseStrategy):
    params = BaseStrategy._base_params + ()

    def __init__(self):  
        super().__init__()  

        # Trade tracking  
        self.trades = {}  # trade_id → trade record  
        self.active_trades = {}  # trade_id → active trade  
        self.counter = {'tp': 0, 'sl': 0}
        
        # Track last processed timestamp to prevent duplicate processing
        # Use timestamp only since bar numbers reset on each run()
        self.last_processed_timestamp = None

    # ----------------------- NEXT -----------------------  
    def next(self):  
        print(f"self.trades: {self.trades}")
        current_bar_time = self.data.datetime.datetime(0)
        current_bar_num = len(self.data)
        is_backfilling_live_mode = Config.live_mode and not getattr(self.data, 'live_mode', False)
        
        # Check if we've already processed this timestamp (prevent duplicate calls)
        # Use timestamp only since bar numbers can change between runs
        if self.last_processed_timestamp == current_bar_time:
            print(f"SKIPPING DUPLICATE next() call - Bar #{current_bar_num} at {current_bar_time}")
            return
        
        # Mark this timestamp as processed
        self.last_processed_timestamp = current_bar_time
        
        super().next()
        
        # Access data_indicators and data_state from cerebro (persists across strategy re-instantiation)
        data_indicators = self._get_data_indicators()
        data_state = self._get_data_state()
        
        if not data_state:
            return
        
        for i, state in data_state.items():
            if i not in data_indicators:
                continue
            data = data_indicators[i]['data']
            current_price = data.close[0]
            log_dict = {
                **state,
                'support': format_price(state['support']),
                'resistance': format_price(state['resistance']),
                'breakout_trend': f'<b>{str(state['breakout_trend'])}</b>' if state['breakout_trend'] is not None else '',
            }
            self.log_to_repo(LogLevel.INFO, f"<b>[{data_indicators[i]['symbol']}={format_price(current_price)}]</b> {'(Backfill)' if is_backfilling_live_mode else '(Live)'}: {log_dict}", RepositoryName.ZONES, date=current_bar_time)
            # if not is_backfilling_live_mode:
            #     self.place_order(data_indicators[i]['data'], OrderType.LIMIT, OrderSide.BUY, 125, 1, 120, 140) 
            if not is_backfilling_live_mode and state['just_broke_out']:
                # Get the data feed for this symbol
                data = data_indicators[i]['data']
                self.place_retest_order_for_data(i)
            self.invalidate_pending_trades_if_sr_changed_or_completed(i)  

    # ----------------------- PLACE RETEST ORDER FOR SPECIFIC DATA FEED -----------------------  
    def place_retest_order_for_data(self, data_index):  
        """Place retest order for a specific data feed."""
        # Access data_indicators and data_state from cerebro (persists across strategy re-instantiation)
        data_indicators = self._get_data_indicators()
        data_state = self._get_data_state()
        
        if data_index not in data_indicators or data_index not in data_state:
            return
        
        # Check if we're in live mode for this data feed
        data = data_indicators[data_index]['data']
        
        if self.broker.getvalue() <= 0:  
            return  
        
        state = data_state[data_index]
        indicators_info = data_indicators[data_index]
        data = indicators_info['data']
        symbol = indicators_info['symbol']
        
        if not state['just_broke_out']:
            return
        
        support = state['support']
        resistance = state['resistance']
        breakout_trend = state['breakout_trend']

        current_position_on_this_symbol = self.open_positions_summary[data_index]
        if breakout_trend == Trend.UPTREND and current_position_on_this_symbol < 0:
            return
        if breakout_trend == Trend.DOWNTREND and current_position_on_this_symbol > 0:
            return
        
        if support is None or resistance is None:
            return
        
        # Avoid trades with too small risk  
        risk_distance = abs(resistance - support)  
        min_risk_distance_price = convert_micropips_to_price(EnvironmentVariables.access_config_value(EnvironmentVariables.MIN_RISK_DISTANCE_MICROPIPS, symbol), symbol)  
        if risk_distance < min_risk_distance_price:  
            return  

        # Determine trade side  
        if breakout_trend == Trend.UPTREND:  
            side = OrderSide.BUY  
            entry_price = resistance  
            sl = support - convert_micropips_to_price(EnvironmentVariables.access_config_value(EnvironmentVariables.SL_BUFFER_MICROPIPS, symbol), symbol)  
            tp = entry_price + risk_distance * self.params.rr  
        else:  
            side = OrderSide.SELL  
            entry_price = support  
            sl = resistance + convert_micropips_to_price(EnvironmentVariables.access_config_value(EnvironmentVariables.SL_BUFFER_MICROPIPS, symbol), symbol)  
            tp = entry_price - risk_distance * self.params.rr  

        size, risk_amount = self.calculate_position_size(risk_distance)  

        # Generate unique trade_id  
        trade_id = str(uuid.uuid4())  

        # Place bracket order on the specific data feed
        orders = self.place_order(data, OrderType.LIMIT, side, entry_price, size, sl, tp)  

        # Check if order was successfully created
        if orders is None or len(orders) == 0 or orders[0] is None:
            print("\n" + "="*80)
            print("⚠️  WARNING: ORDER PLACEMENT FAILED IN STRATEGY ⚠️")
            print("="*80)
            print(f"❌ Failed to place retest order for symbol: {symbol}")
            print(f"   Order side: {side.name}")
            print(f"   Entry price: {format_price(entry_price)}")
            print(f"   Size: {size}")
            print(f"   Stop loss: {format_price(sl)}")
            print(f"   Take profit: {format_price(tp)}")
            print(f"   Support: {format_price(support)}")
            print(f"   Resistance: {format_price(resistance)}")
            print(f"   Breakout trend: {breakout_trend}")
            print(f"   Risk distance: {format_price(risk_distance)}")
            print(f"   Candle index: {self.candle_index}")
            print("   ⚠️  Order NOT placed. Check validation warnings above for details!")
            print("="*80 + "\n")
            self.log_trade(TradeState.CANCELED, self.candle_index, side,
                        f"[{symbol}] Failed to place order: Entry={format_price(entry_price)}, Size={size}, TP={format_price(tp)}, SL={format_price(sl)}")
            return

        main_order = orders[0]
        sl_order   = orders[1] if len(orders) > 1 else None
        tp_order   = orders[2] if len(orders) > 2 else None
        
        # Additional safety check
        if main_order is None:
            print("\n" + "="*80)
            print("⚠️  WARNING: MAIN ORDER IS NONE AFTER PLACEMENT ⚠️")
            print("="*80)
            print(f"❌ Main order is None even though orders list exists")
            print(f"   Symbol: {symbol}")
            print(f"   Order side: {side.name}")
            print(f"   Orders returned: {orders}")
            print(f"   Entry price: {format_price(entry_price)}")
            print(f"   Size: {size}")
            print("   ⚠️  This should not happen! Order structure is invalid!")
            print("="*80 + "\n")
            self.log_trade(TradeState.CANCELED, self.candle_index, side,
                        f"[{symbol}] Main order is None. Order not placed.")
            return

        self.active_trades[main_order.ref] = {
            "main_order_ref": main_order.ref,
            "tp_order_ref": tp_order.ref if tp_order else None,
            "sl_order_ref": sl_order.ref if sl_order else None,
            "order_side": side,
            "state": TradeState.PENDING,
            "entry_price": entry_price,
            "size": size,
            "data_index": data_index,
            "symbol": symbol,
        }
        if tp_order:
            self.active_trades[tp_order.ref] = self.active_trades[main_order.ref]
        if sl_order:
            self.active_trades[sl_order.ref] = self.active_trades[main_order.ref]

        # Store trade record  
        trade_record = {  
            'trade_id': trade_id,  
            'symbol': symbol,
            'order_side': side,  
            'state': TradeState.PENDING,  
            'placed_candle': self.candle_index,  
            'entry_price': entry_price,  
            'size': size,  
            'sl': sl,  
            'tp': tp,  
            'orders': {  
                'main': orders[0] if len(orders) > 0 else None,  
                'tp': orders[1] if len(orders) > 1 else None,  
                'sl': orders[2] if len(orders) > 2 else None  
            },  
            'open_candle': None,  
            'close_candle': None,  
            'pnl': None,  
            'close_reason': None  
        }  

        self.trades[trade_id] = trade_record  
        self.active_trades[trade_id] = trade_record  

        # Map orders to trade_id  
        for o in trade_record['orders'].values():  
            if o:  
                o.trade_id = trade_id  

        # Log pending  
        self.log_trade(TradeState.PENDING, self.candle_index, side,  
                    f"[{symbol}] Entry: {format_price(entry_price)}, Size: {size}, TP: {format_price(tp)}, SL: {format_price(sl)}, Risk: {format_price(risk_amount)}")  

    # ----------------------- INVALIDATE PENDING FOR SPECIFIC DATA FEED -----------------------  
    def invalidate_pending_trades_if_sr_changed_or_completed(self, data_index):
        """Invalidate pending trades for a specific data feed."""
        # Access data_indicators and data_state from cerebro (persists across strategy re-instantiation)
        data_indicators = self._get_data_indicators()
        data_state = self._get_data_state()
        if data_index not in data_state or data_index not in data_indicators:
            return
        state = data_state[data_index]
        support = state['support']
        resistance = state['resistance']
        symbol = data_indicators[data_index]['symbol']
        
        for trade_id, trade in list(self.active_trades.items()):  
            if trade.get('data_index') != data_index:
                continue
            if trade['state'] == TradeState.PENDING:  
                invalidation_price = convert_micropips_to_price(EnvironmentVariables.access_config_value(EnvironmentVariables.SR_CANCELLATION_THRESHOLD_MICROPIPS, symbol), symbol)  
                if trade['order_side'] == OrderSide.BUY and support is not None and trade.get('broken_resistance') is not None:  
                    if support > trade['broken_resistance'] + invalidation_price:  
                        symbol = trade.get('symbol', 'UNKNOWN')
                        self.log_trade(TradeState.CANCELED, self.candle_index, trade['order_side'],  
                                    f"[{symbol}] Invalidated BUY trade {trade_id} due to new support {format_price(support)}")  
                        self._cancel_trade_orders(trade)  
                elif trade['order_side'] == OrderSide.SELL and resistance is not None and trade.get('broken_support') is not None:  
                    if resistance < trade['broken_support'] - invalidation_price:  
                        symbol = trade.get('symbol', 'UNKNOWN')
                        self.log_trade(TradeState.CANCELED, self.candle_index, trade['order_side'],  
                                    f"[{symbol}] Invalidated SELL trade {trade_id} due to new resistance {format_price(resistance)}")  
                        self._cancel_trade_orders(trade)  

    def _cancel_trade_orders(self, trade):  
        for o in trade['orders'].values():  
            if o is not None and o.status in [o.Submitted, o.Accepted]:  
                try:  
                    self.cancel(o)  
                except Exception as e:  
                    self.log(f"Error cancelling order {o.ref}: {e}")  
        self.active_trades.pop(trade['trade_id'], None)  

    def notify_order(self, order):
        if Config.show_debug_logs:
            print(f"*** NOTIFY_ORDER: {order.getstatusname()} - {order.info} - Size: {order.size}, Price: {order.price} ***")
        if order is None:
            return

        # -----------------------------
        # Identify event type
        # -----------------------------
        if order.status == order.Submitted:
            if Config.show_debug_logs:
                print(f"  Order Submitted: {order}")
            return
        if order.status == order.Accepted:
            if Config.show_debug_logs:
                print(f"  Order Accepted: {order}")
            return

        # -----------------------------
        # COMPLETED = fill executed
        # -----------------------------
        if order.status == order.Completed:

            ref = order.ref
            trade_record = self.active_trades.get(ref)

            # Order does NOT belong to a tracked trade
            if trade_record is None:
                print(f"[UNKNOWN] Completed order (ref={ref}) not tracked")
                return

            main_ref   = trade_record["main_order_ref"]
            tp_ref     = trade_record.get("tp_order_ref")
            sl_ref     = trade_record.get("sl_order_ref")

            # -----------------------------
            # MAIN ORDER filled -> RUNNING
            # -----------------------------
            if ref == main_ref:
                # Update the full trade record with open_candle
                if hasattr(order, 'trade_id') and order.trade_id in self.trades:
                    self.trades[order.trade_id]['open_candle'] = self.candle_index
                    self.trades[order.trade_id]['state'] = TradeState.RUNNING
                
                symbol = trade_record.get('symbol', '')
                symbol_str = f"[{symbol}] " if symbol else ""
                self.log_trade(
                    TradeState.RUNNING,
                    self.candle_index,
                    trade_record["order_side"],
                    f"{symbol_str}Main Order Filled | Entry={order.executed.price} | Size={order.executed.size}"
                )
                return

            if ref == tp_ref:
                self._handle_trade_exit(order, trade_record, TradeState.TP_HIT, 'tp', "TP Hit")
                return

            if ref == sl_ref:
                self._handle_trade_exit(order, trade_record, TradeState.SL_HIT, 'sl', "SL Hit")
                return


        if order.status in [order.Canceled, order.Rejected]: # Canceled orders because of invalidation or rejection
            if Config.show_debug_logs:
                print(f"  Order Canceled/Rejected: {order} - Info: {order.info}")
            trade_record = self.active_trades.pop(order.ref, None)

    def _handle_trade_exit(self, order, trade_record, trade_state, counter_key, exit_type):
        """Handle trade exit (TP or SL) with common logic."""
        exit_price = order.executed.price
        entry_price = trade_record["entry_price"]
        size = abs(trade_record["size"])

        if trade_record["order_side"] == OrderSide.BUY:
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

        symbol = trade_record.get('symbol', '')
        symbol_str = f"[{symbol}] " if symbol else ""
        self.log_trade(
            trade_state,
            self.candle_index,
            trade_record["order_side"],
            f"{symbol_str}{exit_type} | Exit={exit_price} | PnL={pnl}"
        )
        self.counter[counter_key] += 1
        
        # Get the full trade record from self.trades if available (has placed_candle and other fields)
        # Orders have trade_id attribute set when created (line 120)
        full_trade_record = None
        if hasattr(order, 'trade_id') and order.trade_id in self.trades:
            full_trade_record = self.trades[order.trade_id].copy()
        else:
            # Fallback to trade_record from active_trades if trade_id not available
            full_trade_record = trade_record.copy()
        
        # Update with exit information
        full_trade_record['pnl'] = pnl
        full_trade_record['close_candle'] = self.candle_index
        if full_trade_record.get('open_candle') is None:
            full_trade_record['open_candle'] = self.candle_index  # Set if not already set
        
        self.add_completed_trade(full_trade_record)
        for ref in [
            trade_record.get("main_order_ref"),
            trade_record.get("tp_order_ref"),
            trade_record.get("sl_order_ref"),
        ]:
            self.active_trades.pop(ref, None)
