from pathlib import Path
import sys

from src.models.trend import Trend
from src.strategies.BaseStrategy import BaseStrategy
from src.models.order import OrderType, TradeState, OrderSide, log_trade
from src.utils.strategy_utils.general_utils import convert_atr_to_price
from utils.logging import format_price
from utils.config import Config
from infrastructure import LogLevel, RepositoryName
from src.utils.environment_variables import EnvironmentVariables
from src.utils.trade_confirmations import RSIConfirmations
import uuid
from src.models.chart_markers import ChartDataType, ChartMarkerType

# Ensure project root on path for ml package
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from ml.AiOrderFilter import AiOrderFilter
from ml.order_filter_features import build_order_filter_features

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

        # self.ai_filter = AiOrderFilter(model_path=str(Path(Config.ai_order_filter_model_path))) 

    # ----------------------- NEXT -----------------------  
    def next(self):  
        current_bar_time = self.data.datetime.datetime(0)
        is_backfilling_live_mode = not self._is_backtesting() and not getattr(self.data, 'live_mode', False)
        
        # Check if we've already processed this timestamp (prevent duplicate calls)
        # Use timestamp only since bar numbers can change between runs
        if self.last_processed_timestamp == current_bar_time:
            return
        
        # Mark this timestamp as processed
        self.last_processed_timestamp = current_bar_time
        
        super().next()
        
        # Access data_indicators and data_state from cerebro (persists across strategy re-instantiation)
        data_indicators = self._get_data_indicators()
        data_state = self._get_data_state()
        
        if not data_state:
            return
        
        for i, pair_state in data_state.items():
            if i not in data_indicators:
                continue
            data = data_indicators[i]['data']
            current_price = data.close[0]
            log_dict = {
                **pair_state,
                'support': format_price(pair_state['support']),
                'resistance': format_price(pair_state['resistance']),
                'breakout_trend': f'<b>{str(pair_state['breakout_trend'])}</b>' if pair_state['breakout_trend'] is not None else '',
            }
            self.log_to_repo(LogLevel.INFO, f"<b>[{data_indicators[i]['symbol']}={format_price(current_price)}]</b> ({'Backtesting' if self._is_backtesting() else 'Backfill' if is_backfilling_live_mode else 'Live'}): {log_dict}", RepositoryName.ZONES, date=current_bar_time)
            daily_rsi = self.indicators['daily_rsi'][0] if self.indicators['daily_rsi'] is not None else None
            ema = data_indicators[i]['ema']
            order_confirmations = [
                pair_state['just_broke_out'],
                # We don't have a current pending limit order on the same symbol and the same zone
                
                ema[0] <= current_price if pair_state['breakout_trend'] == Trend.UPTREND else \
                    ema[0] >= current_price,
                RSIConfirmations.daily_rsi_allows_trade(daily_rsi, pair_state['breakout_trend']) if Config.check_for_daily_rsi else True,
                current_bar_time.weekday() != 0,  # Don't take orders on Monday (0 = Monday)
            ]
            if not is_backfilling_live_mode and all(order_confirmations):
                take_trade = True
                # if self.ai_filter and pair_state.get('support') is not None and pair_state.get('resistance') is not None:
                #     entry_price, sl, tp = self._entry_sl_tp_for_zone(pair_state, data_indicators[i])
                #     if entry_price is not None:
                #         features = build_order_filter_features(
                #             data_indicators[i], pair_state['breakout_trend'], entry_price, sl, tp
                #         )
                #         take_trade = self.ai_filter.predict(features) >= getattr(self.ai_filter, 'best_threshold', 0.5)
                if take_trade:
                    self.place_retest_order_for_data(i)
                    self.set_chart_data(ChartDataType.MARKER, 
                                      data_feed_index=i,
                                      candle_index=self.candle_index, 
                                      price=current_price, 
                                      marker_type=ChartMarkerType.RETEST_ORDER_PLACED)
            self.invalidate_pending_trades_if_sr_changed_or_completed(i)  
            self.process_pending_trade_updates(i)
            
            # Sync current indicator data to chart for live trading visualization
            if not self._is_backtesting():
                self.sync_indicator_data_to_chart(i)

    def process_pending_trade_updates(self, data_index):
        # Update atr_rel_excursion on pending orders for this pair
        data_indicators = self._get_data_indicators()
        data = data_indicators[data_index]['data']
        high_price = data.high[0]
        low_price = data.low[0]
        for trade_key, trade in list(self.active_trades.items()):  
            if trade.get('data_index') != data_index:
                continue
            if trade.get('state') == TradeState.PENDING or trade.get('state') == TradeState.RUNNING or \
                trade.get('open_candle') == self.candle_index:
                if trade.get('order_side') == OrderSide.BUY:
                    trade['highest_excursion_from_breakout'] = max(trade['highest_excursion_from_breakout'], abs(high_price - trade['entry_price']))
                else:
                    trade['highest_excursion_from_breakout'] = max(trade['highest_excursion_from_breakout'], abs(low_price - trade['entry_price']))

    def _entry_sl_tp_for_zone(self, pair_state, indicators):
        """Return (entry_price, sl, tp) for the zone; (None, None, None) if not computable."""
        support = pair_state['support']
        resistance = pair_state['resistance']
        breakout_trend = pair_state['breakout_trend']
        symbol = indicators['symbol']
        atr_val = indicators['atr'][0] if len(indicators['atr']) > 0 else None
        if atr_val is None or atr_val <= 0:
            return (None, None, None)
        risk_distance = abs(resistance - support)
        sl_buffer = convert_atr_to_price(atr_val, EnvironmentVariables.SL_BUFFER_ATR, symbol)
        if breakout_trend == Trend.UPTREND:
            entry_price = resistance
            sl = support - sl_buffer
            tp = entry_price + risk_distance * self.params.rr
        else:
            entry_price = support
            sl = resistance + sl_buffer
            tp = entry_price - risk_distance * self.params.rr
        return (entry_price, sl, tp)

    def place_retest_order_for_data(self, data_index):  
        """Place retest order for a specific data feed."""
        # Access data_indicators and data_state from cerebro (persists across strategy re-instantiation)
        data_indicators = self._get_data_indicators()
        data_state = self._get_data_state()
        
        if data_index not in data_indicators or data_index not in data_state:
            return
        
        # Get the data feed for this symbol
        data = data_indicators[data_index]['data']
        symbol = data_indicators[data_index]['symbol']
        
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
        # if breakout_trend == Trend.UPTREND and current_position_on_this_symbol < 0:
        #     return
        # if breakout_trend == Trend.DOWNTREND and current_position_on_this_symbol > 0:
        #     return
        
        if support is None or resistance is None:
            return
        
        # Avoid trades with too small risk  
        risk_distance = abs(resistance - support)  
        atr_value = data_indicators[data_index]['atr'][0] if len(data_indicators[data_index]['atr']) > 0 else 0.0
        min_risk_distance_price = convert_atr_to_price(atr_value, EnvironmentVariables.MIN_RISK_DISTANCE_ATR, symbol)
        if risk_distance < min_risk_distance_price:  
            return
        order_datetime = data.datetime.datetime(0)
        
        # Get candle_data to verify we're updating the correct candle
        candle_data = self._get_candle_data()
        candle_index = len(candle_data.get(data_index, [])) - 1 if data_index in candle_data and candle_data[data_index] else -1
        
        # Store the datetime in the candle_data so we can verify it matches
        self.set_candle_data(data_feed_index=data_index, order_placed=True, order_datetime=order_datetime)
        
        # Verify the datetime was stored correctly
        stored_datetime = None
        if data_index in candle_data and candle_data[data_index] and candle_index >= 0:
            stored_datetime = candle_data[data_index][candle_index].get('order_datetime')
        
        self.logger.log(LogLevel.INFO, f"Placing retest order for {symbol} (data_index={data_index}) on date {order_datetime}, candle_index={candle_index}, stored_datetime={stored_datetime}", RepositoryName.WIP)  

        # Determine trade side  
        if breakout_trend == Trend.UPTREND:  
            side = OrderSide.BUY  
            entry_price = resistance  
            sl_buffer = convert_atr_to_price(atr_value, EnvironmentVariables.SL_BUFFER_ATR, symbol)
            sl = support - sl_buffer  
            tp = entry_price + risk_distance * self.params.rr  
        else:  
            side = OrderSide.SELL  
            entry_price = support  
            sl_buffer = convert_atr_to_price(atr_value, EnvironmentVariables.SL_BUFFER_ATR, symbol)
            sl = resistance + sl_buffer  
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

        # Note: active_trades lookup structure is set after trade_record creation below

        # Get current datetime for tracking
        current_datetime = data.datetime.datetime(0)
        
        # Track broken support/resistance for invalidation logic
        broken_resistance = resistance if breakout_trend == Trend.UPTREND else None
        broken_support = support if breakout_trend == Trend.DOWNTREND else None
        
        # Store trade record  
        trade_record = {  
            'trade_id': trade_id,  
            'symbol': symbol,
            'order_side': side,  
            'state': TradeState.PENDING,  
            'placed_candle': self.candle_index - 1,
            'placed_datetime': current_datetime,
            'entry_price': entry_price,  # Order price (may differ from executed price)
            'entry_executed_price': None,  # Will be set when order fills
            'size': size,  
            'sl': sl,  
            'tp': tp,  
            'broken_resistance': broken_resistance,  # Track for invalidation
            'broken_support': broken_support,  # Track for invalidation
            'main_order_ref': main_order.ref,
            'tp_order_ref': tp_order.ref if tp_order else None,
            'sl_order_ref': sl_order.ref if sl_order else None,
            'data_index': data_index,  # Store data_index for multi-symbol support
            'orders': {  
                'main': orders[0] if len(orders) > 0 else None,  
                'tp': orders[1] if len(orders) > 1 else None,  
                'sl': orders[2] if len(orders) > 2 else None  
            },  
            'open_candle': None,
            'open_datetime': None,
            'close_candle': None,
            'close_datetime': None,
            'pnl': None,
            'close_reason': None,  # Will be set to 'TP' or 'SL' when trade closes
            # Metadata
            'rsi_at_break': data_indicators[data_index]['rsi'][0],
            'relative_volume': data.volume[0] / data_indicators[data_index]['volume_ma'][0], 
            'atr_breakout_wick': (((data.high[0] - max(data.open[0], data.close[0])) if breakout_trend == Trend.UPTREND else (min(data.open[0], data.close[0]) - data.low[0])) / max(data_indicators[data_index]['atr'][0], 1e-6)),
            'time_to_fill': None,
            'highest_excursion_from_breakout': data.high[0] - entry_price if breakout_trend == Trend.UPTREND else entry_price - data.low[0],
            'atr_sl_dist': abs(sl - entry_price) / data_indicators[data_index]['atr'][0],
            'atr_tp_dist': abs(tp - entry_price) / data_indicators[data_index]['atr'][0],
        }  

        self.trades[trade_id] = trade_record
        
        # Store in active_trades using trade_id (not order.ref) for consistency
        # Also store order refs for quick lookup in notify_order
        self.active_trades[trade_id] = trade_record
        self.active_trades[main_order.ref] = trade_record  # For notify_order lookup
        if tp_order:
            self.active_trades[tp_order.ref] = trade_record
        if sl_order:
            self.active_trades[sl_order.ref] = trade_record  

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
        
        for trade_key, trade in list(self.active_trades.items()):  
            # Skip if this is an order ref lookup (not a trade_id)
            # Order refs are integers, trade_ids are UUID strings
            trade_id = trade.get('trade_id')
            if trade_id is None:
                # This is an order ref entry, skip it (we'll process via trade_id)
                continue
            
            # Only process trades with trade_id matching the key (not order ref lookups)
            if trade_key != trade_id:
                continue
            
            if trade.get('data_index') != data_index:
                continue
            if trade.get('state') == TradeState.PENDING:  
                atr_value = data_indicators[data_index]['atr'][0] if len(data_indicators[data_index]['atr']) > 0 else 0.0
                invalidation_price = convert_atr_to_price(atr_value, EnvironmentVariables.SR_CANCELLATION_THRESHOLD_ATR, symbol)
                trade_id = trade.get('trade_id')
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
        # Update trade state to CANCELED
        trade_id = trade.get('trade_id')
        if trade_id and trade_id in self.trades:
            self.trades[trade_id]['state'] = TradeState.CANCELED
            self.trades[trade_id]['close_reason'] = 'CANCELED'
            self.trades[trade_id]['close_candle'] = self.candle_index
            # Get datetime
            data_index = trade.get('data_index')
            data_indicators = self._get_data_indicators()
            if data_index is not None and data_index in data_indicators:
                data = data_indicators[data_index]['data']
                current_datetime = data.datetime.datetime(0)
            else:
                current_datetime = self.data.datetime.datetime(0)
            self.trades[trade_id]['close_datetime'] = current_datetime
        
        # Cancel orders
        for o in trade.get('orders', {}).values():  
            if o is not None and o.status in [o.Submitted, o.Accepted]:  
                try:  
                    self.cancel(o)  
                except Exception as e:  
                    self.log(f"Error cancelling order {o.ref}: {e}")
        
        # Clean up active_trades - remove all references
        if trade_id:
            self.active_trades.pop(trade_id, None)
        
        # Remove order refs
        main_ref = trade.get("main_order_ref")
        tp_ref = trade.get("tp_order_ref")
        sl_ref = trade.get("sl_order_ref")
        for ref in [main_ref, tp_ref, sl_ref]:
            if ref:
                self.active_trades.pop(ref, None)  

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
            
            # If we got trade_record via order ref, try to get the full record via trade_id
            trade_id = trade_record.get('trade_id')
            if trade_id and trade_id in self.trades:
                # Use the full trade record from self.trades
                trade_record = self.trades[trade_id]

            main_ref   = trade_record.get("main_order_ref")
            tp_ref     = trade_record.get("tp_order_ref")
            sl_ref     = trade_record.get("sl_order_ref")

            # -----------------------------
            # MAIN ORDER filled -> RUNNING
            # -----------------------------
            if ref == main_ref:
                # Get the data feed to get current datetime
                data_index = trade_record.get('data_index')
                data_indicators = self._get_data_indicators()
                if data_index is not None and data_index in data_indicators:
                    data = data_indicators[data_index]['data']
                    current_datetime = data.datetime.datetime(0)
                else:
                    current_datetime = self.data.datetime.datetime(0)
                
                # Update the full trade record with open_candle and executed price
                if hasattr(order, 'trade_id') and order.trade_id in self.trades:
                    self.trades[order.trade_id]['open_candle'] = self.candle_index
                    self.trades[order.trade_id]['open_datetime'] = current_datetime
                    self.trades[order.trade_id]['entry_executed_price'] = order.executed.price
                    self.trades[order.trade_id]['state'] = TradeState.RUNNING
                    
                    # Calculate entry slippage (difference between order price and executed price)
                    entry_price = self.trades[order.trade_id].get('entry_price')
                    if entry_price is not None and order.executed.price is not None:
                        entry_slippage = abs(order.executed.price - entry_price)
                        self.trades[order.trade_id]['entry_slippage'] = entry_slippage
                    
                    # Also update trade_record reference if it's the same object
                    if trade_record.get('trade_id') == order.trade_id:
                        trade_record['open_candle'] = self.candle_index
                        trade_record['open_datetime'] = current_datetime
                        trade_record['entry_executed_price'] = order.executed.price
                        trade_record['state'] = TradeState.RUNNING
                        if 'entry_slippage' in self.trades[order.trade_id]:
                            trade_record['entry_slippage'] = self.trades[order.trade_id]['entry_slippage']
                
                symbol = trade_record.get('symbol', '')
                symbol_str = f"[{symbol}] " if symbol else ""
                self.log_trade(
                    TradeState.RUNNING,
                    self.candle_index,
                    trade_record["order_side"],
                    f"{symbol_str}Main Order Filled | Entry={order.executed.price} | Size={order.executed.size}"
                )
                trade_record['time_to_fill'] = self.candle_index - trade_record['placed_candle'] + 1
                # We have to convert highest_excursion_from_breakout to atr_rel_excursion
                atr = data_indicators[data_index]['atr']
                trade_record['atr_rel_excursion'] = trade_record['highest_excursion_from_breakout'] / atr[0]
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
        # Use executed entry price if available, otherwise fall back to order price
        entry_price = trade_record.get('entry_executed_price') or trade_record.get("entry_price")
        size = abs(trade_record["size"])

        if trade_record["order_side"] == OrderSide.BUY:
            pnl = (exit_price - entry_price) * size
        else:
            pnl = (entry_price - exit_price) * size

        # Get the data feed to get current datetime
        data_index = trade_record.get('data_index')
        data_indicators = self._get_data_indicators()
        if data_index is not None and data_index in data_indicators:
            data = data_indicators[data_index]['data']
            current_datetime = data.datetime.datetime(0)
        else:
            current_datetime = self.data.datetime.datetime(0)

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
        # Orders have trade_id attribute set when created
        full_trade_record = None
        trade_id = None
        if hasattr(order, 'trade_id') and order.trade_id in self.trades:
            trade_id = order.trade_id
            full_trade_record = self.trades[trade_id].copy()
        else:
            # Fallback to trade_record from active_trades if trade_id not available
            trade_id = trade_record.get('trade_id')
            full_trade_record = trade_record.copy()
        
        # Determine close reason
        close_reason = 'TP' if trade_state == TradeState.TP_HIT else 'SL'
        
        # Update with exit information
        full_trade_record['pnl'] = pnl
        full_trade_record['close_candle'] = self.candle_index
        full_trade_record['close_datetime'] = current_datetime
        full_trade_record['close_reason'] = close_reason
        full_trade_record['exit_price'] = exit_price  # Store exit price for reference
        full_trade_record['state'] = trade_state  # Update state
        
        # Ensure open_candle is set (should have been set when main order filled)
        if full_trade_record.get('open_candle') is None:
            # This shouldn't happen, but set it as fallback
            full_trade_record['open_candle'] = full_trade_record.get('placed_candle', self.candle_index)
        if full_trade_record.get('open_datetime') is None:
            full_trade_record['open_datetime'] = full_trade_record.get('placed_datetime', current_datetime)
        
        # Ensure entry_executed_price is set (use entry_price as fallback)
        if full_trade_record.get('entry_executed_price') is None:
            full_trade_record['entry_executed_price'] = full_trade_record.get('entry_price')
        
        # Calculate slippage
        # Entry slippage: difference between order price and executed price
        entry_price = full_trade_record.get('entry_price')
        entry_executed_price = full_trade_record.get('entry_executed_price')
        if entry_price is not None and entry_executed_price is not None:
            entry_slippage = abs(entry_executed_price - entry_price)
            full_trade_record['entry_slippage'] = entry_slippage
        
        # Close slippage: difference between TP/SL order price and executed exit price
        # Get TP/SL price from trade_record (stored when order was placed)
        exit_order_price = None
        if trade_state == TradeState.TP_HIT:
            exit_order_price = trade_record.get('tp')
        elif trade_state == TradeState.SL_HIT:
            exit_order_price = trade_record.get('sl')
        
        # Fallback to order.price if not found in trade_record
        if exit_order_price is None and hasattr(order, 'price') and order.price:
            exit_order_price = order.price
        
        if exit_order_price is not None and exit_price is not None:
            close_slippage = abs(exit_price - exit_order_price)
            full_trade_record['close_slippage'] = close_slippage
        
        # Total slippage cost (in price units, will be multiplied by size later for dollar cost)
        entry_slippage_val = full_trade_record.get('entry_slippage', 0) or 0
        close_slippage_val = full_trade_record.get('close_slippage', 0) or 0
        total_slippage_price = entry_slippage_val + close_slippage_val
        # Total slippage cost in dollars (slippage per unit * position size)
        total_slippage_cost = total_slippage_price * size
        full_trade_record['total_slippage'] = total_slippage_cost
        
        # IMPORTANT: Update the trade in self.trades dict (not just the copy)
        if trade_id and trade_id in self.trades:
            self.trades[trade_id].update(full_trade_record)
        
        self.add_completed_trade(full_trade_record)
        
        # Clean up active_trades - remove all references (by trade_id and order refs)
        trade_id = full_trade_record.get('trade_id')
        if trade_id:
            self.active_trades.pop(trade_id, None)
        
        # Remove order refs
        main_ref = trade_record.get("main_order_ref")
        tp_ref = trade_record.get("tp_order_ref")
        sl_ref = trade_record.get("sl_order_ref")
        for ref in [main_ref, tp_ref, sl_ref]:
            if ref:
                self.active_trades.pop(ref, None)

    # ----------------------- VIEW TRADES -----------------------
    def print_trades(self, include_pending=False):
        """Print all trades in a readable format."""
        print("\n" + "=" * 100)
        print("TRADE LOG")
        print("=" * 100)
        
        if not self.trades:
            print("No trades found in self.trades dictionary.")
            print(f"Total trades in dict: {len(self.trades)}")
            print(f"Completed trades list: {len(self.completed_trades)}")
            return
        
        # Debug: Show what we have
        total_trades = len(self.trades)
        trades_with_pnl = [t for t in self.trades.values() if t.get('pnl') is not None]
        pending_trades = [t for t in self.trades.values() if t.get('state') == TradeState.PENDING]
        running_trades = [t for t in self.trades.values() if t.get('state') == TradeState.RUNNING]
        canceled_trades = [t for t in self.trades.values() if t.get('state') == TradeState.CANCELED]
        
        print(f"Debug: Total trades in dict: {total_trades}")
        print(f"Debug: Trades with PnL (completed): {len(trades_with_pnl)}")
        print(f"Debug: Pending trades: {len(pending_trades)}")
        print(f"Debug: Running trades: {len(running_trades)}")
        print(f"Debug: Canceled trades: {len(canceled_trades)}")
        print(f"Debug: Completed trades list: {len(self.completed_trades)}")
        
        # Show breakdown
        if len(canceled_trades) > 0:
            print(f"\nNote: {len(canceled_trades)} trades were canceled (never filled)")
            print(f"      These are included in CSV export but not shown in completed trades table")
        
        # Filter trades
        if include_pending:
            trades_to_show = list(self.trades.values())
        else:
            trades_to_show = [t for t in self.trades.values() if t.get('pnl') is not None]
        
        if not trades_to_show:
            print("\nNo completed trades found (trades with PnL).")
            print("Showing all trades for debugging:")
            for trade_id, trade in list(self.trades.items())[:5]:  # Show first 5
                print(f"  Trade {trade_id[:8]}: state={trade.get('state')}, pnl={trade.get('pnl')}, close_reason={trade.get('close_reason')}")
            return
        
        # Sort by placed_candle
        trades_to_show.sort(key=lambda x: x.get('placed_candle', 0))
        
        print(f"\nTotal Trades: {len(trades_to_show)}")
        print(f"{'ID':<10} {'Symbol':<10} {'Side':<6} {'State':<12} {'Entry':<12} {'Exit':<12} {'PnL':<12} {'Reason':<10} {'Placed':<20} {'Opened':<20} {'Closed':<20}")
        print("-" * 100)
        
        for trade in trades_to_show:
            trade_id = trade.get('trade_id', 'N/A')[:8]  # Short ID
            symbol = trade.get('symbol', 'N/A')
            side = trade.get('order_side', OrderSide.BUY).name if isinstance(trade.get('order_side'), OrderSide) else str(trade.get('order_side', 'N/A'))
            state = trade.get('state', 'N/A')
            if isinstance(state, TradeState):
                state = state.name
            
            entry_price = trade.get('entry_executed_price') or trade.get('entry_price', 0)
            exit_price = trade.get('exit_price', 'N/A')
            pnl = trade.get('pnl', 'N/A')
            close_reason = trade.get('close_reason', 'N/A')
            
            placed_dt = trade.get('placed_datetime', 'N/A')
            if placed_dt != 'N/A' and placed_dt:
                placed_str = placed_dt.strftime('%Y-%m-%d %H:%M') if hasattr(placed_dt, 'strftime') else str(placed_dt)
            else:
                placed_str = f"Candle {trade.get('placed_candle', 'N/A')}"
            
            open_dt = trade.get('open_datetime', 'N/A')
            if open_dt != 'N/A' and open_dt:
                open_str = open_dt.strftime('%Y-%m-%d %H:%M') if hasattr(open_dt, 'strftime') else str(open_dt)
            else:
                open_str = f"Candle {trade.get('open_candle', 'N/A')}"
            
            close_dt = trade.get('close_datetime', 'N/A')
            if close_dt != 'N/A' and close_dt:
                close_str = close_dt.strftime('%Y-%m-%d %H:%M') if hasattr(close_dt, 'strftime') else str(close_dt)
            else:
                close_str = f"Candle {trade.get('close_candle', 'N/A')}"
            
            print(f"{trade_id:<10} {symbol:<10} {side:<6} {state:<12} {format_price(entry_price):<12} {str(exit_price):<12} {str(pnl):<12} {str(close_reason):<10} {placed_str:<20} {open_str:<20} {close_str:<20}")
        
        print("=" * 100 + "\n")
    
    def get_all_trades(self):
        """Get all trades as a list."""
        return list(self.trades.values())
    
    def get_completed_trades(self):
        """Get only completed trades (with PnL)."""
        return [t for t in self.trades.values() if t.get('pnl') is not None]
    
    def get_pending_trades(self):
        """Get pending trades."""
        return [t for t in self.trades.values() if t.get('state') == TradeState.PENDING]
    
    def get_running_trades(self):
        """Get running trades."""
        return [t for t in self.trades.values() if t.get('state') == TradeState.RUNNING]
    
    def verify_trades(self, verbose=False):
        completed_trades = self.get_completed_trades()
        
        if not completed_trades:
            if verbose:
                print("No completed trades to verify.")
            return True  # No trades means nothing to verify, so checks pass
        
        if verbose:
            print(f"\n{'='*80}")
            print(f"TRADE VERIFICATION - {len(completed_trades)} TRADES")
            print(f"{'='*80}\n")
        
        issues = []
        verified_count = 0
        
        for i, trade in enumerate(completed_trades, 1):
            trade_id = trade.get('trade_id', 'N/A')[:8]
            symbol = trade.get('symbol', 'N/A')
            side = trade.get('order_side')
            side_name = side.name if isinstance(side, OrderSide) else str(side)
            
            entry_price = trade.get('entry_executed_price') or trade.get('entry_price')
            exit_price = trade.get('exit_price')
            size = abs(trade.get('size', 0))
            pnl = trade.get('pnl')
            close_reason = trade.get('close_reason')
            tp = trade.get('tp')
            sl = trade.get('sl')
            
            # Calculate expected PnL
            if entry_price and exit_price:
                if side == OrderSide.BUY:
                    expected_pnl = (exit_price - entry_price) * size
                else:  # SELL
                    expected_pnl = (entry_price - exit_price) * size
            else:
                expected_pnl = None
            
            # Check PnL
            pnl_ok = True
            if pnl is not None and expected_pnl is not None:
                diff = abs(pnl - expected_pnl)
                if diff > 0.01:
                    pnl_ok = False
                    issues.append(f"Trade {trade_id}: PnL mismatch - Expected: {expected_pnl:.2f}, Got: {pnl:.2f}, Diff: {diff:.2f}")
            
            # Check exit price matches TP/SL (allow small slippage)
            exit_ok = True
            if exit_price:
                if close_reason == 'TP' and tp:
                    diff = abs(exit_price - tp)
                    if diff > 0.0001:  # Allow 0.1 pip difference for slippage
                        exit_ok = False
                        issues.append(f"Trade {trade_id}: Exit price doesn't match TP - Expected: {tp:.5f}, Got: {exit_price:.5f}, Diff: {diff:.5f}")
                elif close_reason == 'SL' and sl:
                    diff = abs(exit_price - sl)
                    if diff > 0.0001:  # Allow 0.1 pip difference for slippage
                        exit_ok = False
                        issues.append(f"Trade {trade_id}: Exit price doesn't match SL - Expected: {sl:.5f}, Got: {exit_price:.5f}, Diff: {diff:.5f}")
            
            # Check timeline
            timeline_ok = True
            placed_candle = trade.get('placed_candle')
            open_candle = trade.get('open_candle')
            close_candle = trade.get('close_candle')
            
            if placed_candle is not None and open_candle is not None:
                if open_candle < placed_candle:
                    timeline_ok = False
                    issues.append(f"Trade {trade_id}: Opened before placed (open_candle: {open_candle} < placed_candle: {placed_candle})")
            
            if open_candle is not None and close_candle is not None:
                if close_candle < open_candle:
                    timeline_ok = False
                    issues.append(f"Trade {trade_id}: Closed before opened (close_candle: {close_candle} < open_candle: {open_candle})")
            
            # Print status
            if pnl_ok and exit_ok and timeline_ok:
                verified_count += 1
                status = "✅"
            else:
                status = "⚠️"
            
            if verbose:
                print(f"{status} Trade {trade_id}: {symbol} {side_name} | Entry: {entry_price:.5f} | Exit: {exit_price:.5f} | PnL: {pnl:.2f} | {close_reason}")
                if not pnl_ok:
                    print(f"   ⚠️  PnL mismatch: Expected {expected_pnl:.2f}, Got {pnl:.2f}")
                if not exit_ok:
                    expected_exit = tp if close_reason == 'TP' else sl
                    print(f"   ⚠️  Exit price mismatch: Expected {expected_exit:.5f}, Got {exit_price:.5f}")
        
        if verbose:
            print(f"\n{'='*80}")
            print(f"VERIFICATION SUMMARY")
            print(f"{'='*80}")
            print(f"Total Trades: {len(completed_trades)}")
            print(f"Verified Correctly: {verified_count}")
            print(f"Issues Found: {len(issues)}")
            
            if issues:
                print(f"\n⚠️  ISSUES FOUND:")
                for issue in issues:
                    print(f"   - {issue}")
            else:
                print(f"\n✅ ALL TRADES VERIFIED CORRECTLY!")
            print(f"{'='*80}\n")
        
        # Return True if no issues found, False otherwise
        return len(issues) == 0
