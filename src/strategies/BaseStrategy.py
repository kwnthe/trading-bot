import backtrader as bt
import csv
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from indicators import BreakoutIndicator
from indicators import BreakRetestIndicator
from models.candlestick import Candlestick
from src.models.chart_markers import ChartDataType, ChartData, ChartDataPoint, ChartMarkerType
from src.models.order import OrderType, TradeState
from utils.config import Config
from utils.strategy_utils.general_utils import convert_pips_to_price
from infrastructure import StrategyLogger, RepositoryType, LogLevel, RepositoryName
from utils.logging import configure_windows_console_for_utf8

configure_windows_console_for_utf8()

class BaseStrategy(bt.Strategy):
    # Store the original params tuple for inheritance
    _base_params = (
        ('symbol', None),
        ('risk_per_trade', Config.risk_per_trade),
        ('rr', Config.rr),
    )
    
    params = _base_params

    def __init__(self):
        self.candle_index = 0
        self.current_candle = None
        self.open_positions_summary = {} # Tracks the current position on each data feed
        self.trades = {}
        self.logger = StrategyLogger.get_logger()
        self.mode = Config.mode
        
        # Get cerebro to access daily_data_mapping
        cerebro = getattr(self.broker, '_owner', None)
        if cerebro is None:
            cerebro = getattr(self.broker, 'cerebro', None)
        
        # Find daily resampled data feed for the first data feed (for backward compatibility)
        # Daily data feed will have '_DAILY' suffix in its name
        daily_data = None
        if cerebro is not None and hasattr(cerebro, 'daily_data_mapping'):
            # Use the mapping if available (maps original data index to daily data)
            daily_data = cerebro.daily_data_mapping.get(0, None)
        
        # Fallback: search by name if mapping not available
        if daily_data is None:
            for data in self.datas:
                data_name = getattr(data, '_name', '')
                if '_DAILY' in data_name.upper():
                    daily_data = data
                    break
        
        # Initialize indicators dictionary for cleaner organization
        regular_rsi_data_source = self.data.close
        
        self.indicators = {
            'rsi': bt.indicators.RSI(
                regular_rsi_data_source,
                period=14
            ),
            'ema': bt.indicators.EMA(
                self.data.close,
                period=Config.ema_length
            ),
        }
        
        # Store reference to daily data for potential future use
        self.daily_data = daily_data
        
        # Initialize daily RSI indicator if daily data is available
        if daily_data is not None:
            # Create RSI indicator directly on daily_data feed
            self.indicators['daily_rsi'] = bt.indicators.RSI(
                daily_data.close,
                period=14
            )
            print(f"Daily data feed available: {getattr(daily_data, '_name', 'unknown')}")
        else:
            self.indicators['daily_rsi'] = None
            print("Daily RSI not initialized - daily_data is None")

        # Access cerebro through broker's _owner attribute
        cerebro = getattr(self.broker, '_owner', None)
        if cerebro is None:
            # Fallback: try to get cerebro from broker's parent
            cerebro = getattr(self.broker, 'cerebro', None)
        
        # Store indicators and state per data feed in cerebro to persist across strategy re-instantiation
        if cerebro is not None:
            if not hasattr(cerebro, 'data_indicators'):
                cerebro.data_indicators = {}
            if not hasattr(cerebro, 'data_state'):
                cerebro.data_state = {}
            if not hasattr(cerebro, 'candle_data'):
                # Candle data storage: dict of lists, one list per data feed
                # Each list contains dicts, one per candle, storing arbitrary data (e.g., {'order_placed': True})
                # This data can be extracted by plot.py for visualization
                cerebro.candle_data = {}
            if not hasattr(cerebro, 'chart_markers'):
                # Chart markers storage: dict of dicts, one dict per data feed ID
                # Each dict maps candle_index -> marker info (price, type, etc.)
                # Example: {0: {100: {'price': 50000.0, 'type': ChartMarkerType.RETEST_ORDER_PLACED}, 150: {'price': 51000.0, 'type': ChartMarkerType.RETEST_ORDER_PLACED}}}
                # Structure: {data_feed_index: {candle_index: {'price': float, 'type': str, ...}}}
                cerebro.chart_markers = {}
            
            # Initialize indicators for all data feeds
            # Get daily data mapping if available
            daily_data_mapping = getattr(cerebro, 'daily_data_mapping', {}) if cerebro is not None else {}
            
            # Track original data feed index (excluding daily resampled feeds)
            original_data_index = 0
            
            for data in self.datas:
                symbol = getattr(data, '_name', self.params.symbol or f'SYMBOL_{original_data_index}')
                # Skip daily data feeds (they have '_DAILY' in name)
                if '_DAILY' in symbol.upper():
                    continue
                
                # Only initialize if not already present (to preserve state across runs)
                if original_data_index not in cerebro.data_indicators:
                    cerebro.data_indicators[original_data_index] = {
                        'breakout': BreakoutIndicator(data, symbol=symbol),
                        'break_retest': BreakRetestIndicator(data, symbol=symbol),
                        'atr': bt.indicators.ATR(data, period=Config.atr_length),
                        'ema': bt.indicators.EMA(data.close, period=Config.ema_length),
                        'volume_ma': bt.indicators.SMA(data.volume, period=Config.volume_ma_length),
                        'rsi': bt.indicators.RSI(data.close, period=14),
                        'symbol': symbol,
                        'data': data
                    }
                
                if original_data_index not in cerebro.data_state:
                    cerebro.data_state[original_data_index] = {
                        'just_broke_out': None,
                        'breakout_trend': None,
                        'support': None,
                        'resistance': None,
                    }
                if original_data_index not in cerebro.candle_data:
                    cerebro.candle_data[original_data_index] = []
                if original_data_index not in cerebro.chart_markers:
                    cerebro.chart_markers[original_data_index] = {}
                
                original_data_index += 1
            
            # Store Zones indicators in self.indicators for cleaner access
            # For backward compatibility, keep main indicators pointing to first data feed
            if 0 in cerebro.data_indicators:
                self.breakout_indicator = cerebro.data_indicators[0]['breakout']
                self.break_retest_indicator = cerebro.data_indicators[0]['break_retest']
                self.indicators['volume_ma'] = cerebro.data_indicators[0]['volume_ma']
                self.indicators['support_resistances'] = {
                    'breakout': self.breakout_indicator,
                    'break_retest': self.break_retest_indicator
                }
        
        # Backward compatibility: expose indicators as direct attributes
        # This allows existing code like strategy.ema or strategy.rsi to continue working
        self.rsi = self.indicators.get('rsi')
        self.ema = self.indicators.get('ema')
        self.atr = self.indicators.get('atr')
        self.volume_ma = self.indicators.get('volume_ma')
        self.daily_rsi = self.indicators.get('daily_rsi')
        
        self.just_broke_out = None
        self.breakout_trend = None
        self.current_candle = None
        self.support = None
        self.resistance = None
        self.initial_cash = None
        self.current_cash = None
        self.unrealized_pnl = 0
        self.completed_trades = []
        self.counter = {'tp': 0, 'sl': 0}

        
    def start(self):
        """Called when the strategy starts - track initial cash"""
        self.initial_cash = self.broker.getvalue()
        self.current_cash = self.initial_cash
    
    def _is_backtesting(self):
        return self.mode == 'backtest'
        
    def _get_cerebro(self):
        """Get cerebro instance from broker."""
        cerebro = getattr(self.broker, '_owner', None)
        if cerebro is None:
            cerebro = getattr(self.broker, 'cerebro', None)
        return cerebro
    
    def _get_data_indicators(self):
        """Get data_indicators from cerebro or broker fallback."""
        cerebro = self._get_cerebro()
        if cerebro is not None and hasattr(cerebro, 'data_indicators'):
            return cerebro.data_indicators
        elif hasattr(self.broker, 'data_indicators'):
            return self.broker.data_indicators
        return {}
    
    def _get_data_state(self):
        """Get data_state from cerebro or broker fallback."""
        cerebro = self._get_cerebro()
        if cerebro is not None and hasattr(cerebro, 'data_state'):
            return cerebro.data_state
        elif hasattr(self.broker, 'data_state'):
            return self.broker.data_state
        return {}
    
    def _get_candle_data(self):
        """Get candle_data from cerebro or broker fallback."""
        cerebro = self._get_cerebro()
        if cerebro is not None and hasattr(cerebro, 'candle_data'):
            return cerebro.candle_data
        elif hasattr(self.broker, 'candle_data'):
            return self.broker.candle_data
        return {}
    
    def next(self):
        self.candle_index = len(self.data) 
        
        self.update_open_positions_summary()
        
        # Get cerebro instance
        cerebro = self._get_cerebro()
        data_indicators = self._get_data_indicators()
        data_state = self._get_data_state()
        candle_data = self._get_candle_data()
        
        # Process all data feeds and update state for each
        for i, indicators_info in data_indicators.items():
            data = indicators_info['data']
            breakout_ind = indicators_info['breakout']
            
            # Initialize data dict for this candle for this data feed
            if i not in candle_data:
                candle_data[i] = []
            candle_data[i].append({})
            
            # Update state for this data feed
            just_broke_out, breakout_trend = breakout_ind.just_broke_out()
            support = breakout_ind.lines.support1[0]
            resistance = breakout_ind.lines.resistance1[0]
            
            # Store in cerebro if available, otherwise broker
            if cerebro is not None:
                if not hasattr(cerebro, 'data_state'):
                    cerebro.data_state = {}
                if not hasattr(cerebro, 'candle_data'):
                    cerebro.candle_data = {}
                cerebro.data_state[i] = cerebro.data_state.get(i, {})
                cerebro.data_state[i]['just_broke_out'] = just_broke_out
                cerebro.data_state[i]['breakout_trend'] = breakout_trend
                cerebro.data_state[i]['support'] = support
                cerebro.data_state[i]['resistance'] = resistance
                cerebro.candle_data[i] = candle_data.get(i, [])
            else:
                if not hasattr(self.broker, 'data_state'):
                    self.broker.data_state = {}
                if not hasattr(self.broker, 'candle_data'):
                    self.broker.candle_data = {}
                if not hasattr(self.broker, 'chart_markers'):
                    self.broker.chart_markers = {}
                self.broker.data_state[i] = self.broker.data_state.get(i, {})
                self.broker.data_state[i]['just_broke_out'] = just_broke_out
                self.broker.data_state[i]['breakout_trend'] = breakout_trend
                self.broker.data_state[i]['support'] = support
                self.broker.data_state[i]['resistance'] = resistance
                self.broker.candle_data[i] = candle_data.get(i, [])
                if i not in self.broker.chart_markers:
                    self.broker.chart_markers[i] = {}
        
        # Get updated state
        data_state = self._get_data_state()
        
        # For backward compatibility, keep main state pointing to first data feed
        self.current_candle = Candlestick.from_bt(self.data, 0)
        if 0 in data_state:
            self.just_broke_out = data_state[0]['just_broke_out']
            self.breakout_trend = data_state[0]['breakout_trend']
            self.support = data_state[0]['support']
            self.resistance = data_state[0]['resistance']
        
        # Calculate uPnl & current cash (aggregate across all positions)
        total_unrealized_pnl = 0
        for i, indicators_info in data_indicators.items():
            data = indicators_info['data']
            open_position = self.getposition(data)
            if open_position.size != 0:
                total_unrealized_pnl += open_position.size * (data.close[0] - open_position.price)
        
        self.unrealized_pnl = total_unrealized_pnl
        self.current_cash = self.broker.getvalue() + self.unrealized_pnl

    def get_trade_summary(self):
        if not self.trades:
            return "No completed trades yet"
        
        total_trades = len(self.trades)
        total_pnl = sum([t['pnl'] for t in self.trades.values() if 'pnl' in t])
        
        return f"Total trades: {total_trades}, Total PnL: {total_pnl:.2f}"
    
    def add_trade(self, trade):
        self.trades[trade.ref] = trade
    
    def add_completed_trade(self, trade):
        self.completed_trades.append(trade)

    def place_order(self, data: bt.LineSeries, order_type: OrderType, order_side: OrderSide, price: float, size: float, sl: float, tp: float):
        """
        Place a bracket order.
        
        Args:
            order_type: Type of order (LIMIT, STOP, MARKET)
            order_side: BUY or SELL
            price: Entry price
            size: Position size
            sl: Stop loss price
            tp: Take profit price
            data: Optional data feed to place order on (defaults to self.data, which is the first symbol)
                  To place on a specific symbol, use:
                  - self.get_data_by_symbol('BTCUSD') to get BTCUSD data feed
                  - cerebro.data_indicators[i]['data'] to get data feed by index (where cerebro = self._get_cerebro())
                  
        Example:
            # Place order on BTCUSD
            btc_data = self.get_data_by_symbol('BTCUSD')
            self.place_order(OrderType.LIMIT, OrderSide.BUY, 50000, 1, 49000, 51000, data=btc_data)
            
            # Place order on SOLUSD
            sol_data = self.get_data_by_symbol('SOLUSD')
            self.place_order(OrderType.LIMIT, OrderSide.BUY, 125, 1, 120, 130, data=sol_data)
        """
        # Validate inputs before placing order
        if size <= 0:
            print("\n" + "="*80)
            print("⚠️  WARNING: INVALID ORDER SIZE ⚠️")
            print("="*80)
            print(f"❌ Order size is invalid: {size}")
            print(f"   Order side: {order_side.name}")
            print(f"   Entry price: {price}")
            print(f"   Stop loss: {sl}")
            print(f"   Take profit: {tp}")
            print("   ⚠️  Order NOT placed. This indicates a problem with position sizing calculation!")
            print("="*80 + "\n")
            self.log(f"⚠️ WARNING: Invalid order size: {size}. Order not placed.")
            return None
        
        if price <= 0 or sl <= 0 or tp <= 0:
            print("\n" + "="*80)
            print("⚠️  WARNING: INVALID PRICES ⚠️")
            print("="*80)
            print(f"❌ One or more prices are invalid:")
            print(f"   Entry price: {price}")
            print(f"   Stop loss: {sl}")
            print(f"   Take profit: {tp}")
            print(f"   Order side: {order_side.name}")
            print("   ⚠️  Order NOT placed. This indicates a problem with price calculation!")
            print("="*80 + "\n")
            self.log(f"⚠️ WARNING: Invalid prices: price={price}, sl={sl}, tp={tp}. Order not placed.")
            return None
        
        # Validate price relationships for bracket orders
        if order_side == OrderSide.BUY:
            # For BUY: entry should be between SL (below) and TP (above), or at least TP should be above entry
            if tp <= price:
                print("\n" + "="*80)
                print("⚠️  WARNING: INVALID BUY BRACKET ORDER ⚠️")
                print("="*80)
                print(f"❌ Take Profit ({tp}) must be ABOVE entry price ({price}) for BUY orders")
                print(f"   Entry price: {price}")
                print(f"   Stop loss: {sl}")
                print(f"   Take profit: {tp}")
                print("   ⚠️  Order NOT placed. This indicates a problem with TP calculation!")
                print("="*80 + "\n")
                self.log(f"⚠️ WARNING: Invalid BUY bracket: TP ({tp}) must be above entry ({price}). Order not placed.")
                return None
            if sl >= price:
                print("\n" + "="*80)
                print("⚠️  WARNING: INVALID BUY BRACKET ORDER ⚠️")
                print("="*80)
                print(f"❌ Stop Loss ({sl}) must be BELOW entry price ({price}) for BUY orders")
                print(f"   Entry price: {price}")
                print(f"   Stop loss: {sl}")
                print(f"   Take profit: {tp}")
                print("   ⚠️  Order NOT placed. This indicates a problem with SL calculation!")
                print("="*80 + "\n")
                self.log(f"⚠️ WARNING: Invalid BUY bracket: SL ({sl}) must be below entry ({price}). Order not placed.")
                return None
        else:  # SELL
            # For SELL: entry should be between TP (below) and SL (above), or at least SL should be above entry
            if sl <= price:
                print("\n" + "="*80)
                print("⚠️  WARNING: INVALID SELL BRACKET ORDER ⚠️")
                print("="*80)
                print(f"❌ Stop Loss ({sl}) must be ABOVE entry price ({price}) for SELL orders")
                print(f"   Entry price: {price}")
                print(f"   Stop loss: {sl}")
                print(f"   Take profit: {tp}")
                print("   ⚠️  Order NOT placed. This indicates a problem with SL calculation!")
                print("="*80 + "\n")
                self.log(f"⚠️ WARNING: Invalid SELL bracket: SL ({sl}) must be above entry ({price}). Order not placed.")
                return None
            if tp >= price:
                print("\n" + "="*80)
                print("⚠️  WARNING: INVALID SELL BRACKET ORDER ⚠️")
                print("="*80)
                print(f"❌ Take Profit ({tp}) must be BELOW entry price ({price}) for SELL orders")
                print(f"   Entry price: {price}")
                print(f"   Stop loss: {sl}")
                print(f"   Take profit: {tp}")
                print("   ⚠️  Order NOT placed. This indicates a problem with TP calculation!")
                print("="*80 + "\n")
                self.log(f"⚠️ WARNING: Invalid SELL bracket: TP ({tp}) must be below entry ({price}). Order not placed.")
                return None
        
        bracket_fn = self.buy_bracket if order_side == OrderSide.BUY else self.sell_bracket
        order_type_mapping = {
            OrderType.LIMIT: bt.Order.Limit,
            OrderType.STOP: bt.Order.Stop,
            OrderType.MARKET: bt.Order.Market,
        }

        try:
            orders = bracket_fn(
                data=data,
                price=price,
                size=size,
                exectype=order_type_mapping[order_type],
                limitprice=tp,
                stopprice=sl,
                valid=None
            )
        except Exception as e:
            print("\n" + "="*80)
            print("⚠️  WARNING: EXCEPTION DURING ORDER PLACEMENT ⚠️")
            print("="*80)
            print(f"❌ Exception occurred while placing bracket order:")
            print(f"   Error: {type(e).__name__}: {e}")
            print(f"   Order side: {order_side.name}")
            print(f"   Entry price: {price}")
            print(f"   Size: {size}")
            print(f"   Stop loss: {sl}")
            print(f"   Take profit: {tp}")
            print("   ⚠️  Order NOT placed. This indicates a broker/system error!")
            print("="*80 + "\n")
            self.log(f"⚠️ WARNING: Error placing bracket order: {e}. Order not placed.")
            return None
        
        # Check if order was successfully created
        if orders is None:
            print("\n" + "="*80)
            print("⚠️  WARNING: BRACKET ORDER RETURNED NONE ⚠️")
            print("="*80)
            print(f"❌ Bracket order function returned None (order rejected by broker)")
            print(f"   Order side: {order_side.name}")
            print(f"   Entry price: {price}")
            print(f"   Size: {size}")
            print(f"   Stop loss: {sl}")
            print(f"   Take profit: {tp}")
            print("   ⚠️  Order NOT placed. Possible reasons:")
            print("      - Insufficient funds/margin")
            print("      - Invalid order parameters")
            print("      - Broker rejection")
            print("="*80 + "\n")
            self.log(f"⚠️ WARNING: Bracket order returned None. Order not placed.")
            return None
        
        if len(orders) == 0 or orders[0] is None:
            print("\n" + "="*80)
            print("⚠️  WARNING: BRACKET ORDER FAILED TO CREATE MAIN ORDER ⚠️")
            print("="*80)
            print(f"❌ Bracket order returned empty list or None main order")
            print(f"   Orders returned: {orders}")
            print(f"   Order side: {order_side.name}")
            print(f"   Entry price: {price}")
            print(f"   Size: {size}")
            print(f"   Stop loss: {sl}")
            print(f"   Take profit: {tp}")
            print("   ⚠️  Order NOT placed. This indicates a broker/system error!")
            print("="*80 + "\n")
            self.log(f"⚠️ WARNING: Bracket order failed to create main order. Order not placed.")
            return None

        # Store TP/SL in the main order's info so the broker can access it
        # This is needed because order.bracket might not be accessible when order is submitted
        if orders and len(orders) > 0 and orders[0] is not None:
            main_order = orders[0]
            
            # Extract TP/SL from child orders if not provided (backup method)
            if tp is None and len(orders) > 1 and orders[1] is not None:
                tp_order = orders[1]
                if hasattr(tp_order, 'price') and tp_order.price:
                    tp = tp_order.price
            if sl is None and len(orders) > 2 and orders[2] is not None:
                sl_order = orders[2]
                if hasattr(sl_order, 'price') and sl_order.price:
                    sl = sl_order.price
            
            # Store in order.info
            if not hasattr(main_order, 'info') or main_order.info is None:
                main_order.info = {}
            main_order.info['tp'] = tp
            main_order.info['sl'] = sl
            main_order.info['is_bracket'] = True
            
            # Also try to store in broker's bracket_tp_sl if broker supports it
            # Access broker through the strategy's broker attribute
            # IMPORTANT: Store immediately so broker can access it when order is submitted
            # print(f"*** ATTEMPTING TO STORE TP/SL: order.ref={main_order.ref}, TP={tp}, SL={sl}, hasattr(broker)={hasattr(self, 'broker')} ***")
            if hasattr(self, 'broker'):
                # print(f"*** BROKER TYPE: {type(self.broker)} ***")
                if hasattr(self.broker, 'store_bracket_tp_sl'):
                    self.broker.store_bracket_tp_sl(main_order.ref, tp, sl)
                    # print(f"*** STORED TP/SL IN BROKER (via method): order.ref={main_order.ref}, TP={tp}, SL={sl} ***")
                elif hasattr(self.broker, 'bracket_tp_sl'):
                    self.broker.bracket_tp_sl[main_order.ref] = {'tp': tp, 'sl': sl}
                    # print(f"*** STORED TP/SL IN BROKER (direct): order.ref={main_order.ref}, TP={tp}, SL={sl} ***")
                    # print(f"*** VERIFIED STORAGE: {main_order.ref in self.broker.bracket_tp_sl} ***")
                else:
                    # print(f"*** BROKER DOES NOT HAVE bracket_tp_sl attribute ***")
                    pass
            else:
                # print(f"*** STRATEGY DOES NOT HAVE BROKER ATTRIBUTE ***")
                pass
        return orders
    
    def calculate_position_size(self, risk_distance: float) -> float:
        # Percentage-based position sizing: Always risk X% of CURRENT CASH (not equity)
        # This creates compounding position sizing where position sizes grow as cash grows.
        # 
        # Example:
        # - Trade 1: $100k cash → risk 1% = $1k → 500k units
        # - Trade 10: $150k cash → risk 1% = $1.5k → 750k units (grows with cash)
        # - Trade 30: $300k cash → risk 1% = $3k → 1.5M units (grows with cash)
        #
        # This is a valid approach (percentage-based risk management) but creates exponential growth.
        # Use getcash() to get current available cash (without unrealized PnL from open positions).
        # This bases position sizing on available cash, not total equity.
        current_cash = self.current_cash
        
        if current_cash <= 0:
            return 0, 0
        # Reduce effective risk per trade when using realistic execution to account for higher costs
        from src.utils.execution_simulator import RealisticExecutionBroker
        is_realistic_broker = isinstance(self.broker, RealisticExecutionBroker)
        effective_risk_per_trade = self.params.risk_per_trade * (0.7 if is_realistic_broker else 1.0)  # 30% reduction for realistic execution
        risk_amount = current_cash * effective_risk_per_trade
        
        # Account for slippage in position sizing
        # This reduces position size to ensure actual risk (including slippage) stays within target
        # This is CRITICAL when using realistic execution simulation
        # Check if we're using realistic execution broker
        from src.utils.execution_simulator import RealisticExecutionBroker
        is_realistic_broker = isinstance(self.broker, RealisticExecutionBroker)
        
        if is_realistic_broker:
            # When using realistic execution, account for slippage
            # Increased slippage buffer to account for higher execution costs
            # This reduces position sizes to keep actual risk at intended percentage
            slippage_pips = 4.0  # Increased to 4.0 to account for higher slippage and spread costs
            slippage_price = convert_pips_to_price(slippage_pips)
            adjusted_risk_distance = risk_distance + slippage_price
            return int(risk_amount / adjusted_risk_distance) if adjusted_risk_distance > 0 else 100000, risk_amount
        
        return int(risk_amount / risk_distance) if risk_distance > 0 else 100000, risk_amount

    def export_trades_to_csv(self, filename=None):
        """Export all completed trades to CSV file"""
        # Get only completed trades (those with pnl set)
        completed_trades = [t for t in self.trades.values() if t.get('pnl') is not None]
        
        if not completed_trades:
            self.log("No completed trades to export")
            return None
        
        self.log(f"Exporting {len(completed_trades)} completed trades to CSV")
        
        # Get backtest metadata from cerebro if available
        cerebro = self._get_cerebro()
        if filename is None:
            if cerebro and hasattr(cerebro, 'backtest_metadata'):
                # Use generate_csv_filename with backtest metadata
                metadata = cerebro.backtest_metadata
                symbol = metadata.get('symbol', self.params.symbol or 'UNKNOWN')
                timeframe = metadata.get('timeframe')
                start_date = metadata.get('start_date')
                end_date = metadata.get('end_date')
                
                if timeframe and start_date and end_date:
                    # Import generate_csv_filename
                    from src.utils.backtesting import generate_csv_filename
                    filepath = generate_csv_filename(symbol, timeframe, start_date, end_date, type_="results")
                    # Ensure directory exists
                    filepath.parent.mkdir(parents=True, exist_ok=True)
                    filepath = str(filepath)  # Convert Path to string for compatibility
                else:
                    # Fallback: use manual path construction
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    backtests_dir = os.path.join(project_root, 'data', 'backtests','results')
                    os.makedirs(backtests_dir, exist_ok=True)
                    filename = f"rr_{self.params.rr}.csv"
                    filepath = os.path.join(backtests_dir, filename)
            else:
                # Fallback: use manual path construction
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                backtests_dir = os.path.join(project_root, 'data', 'backtests','results')
                os.makedirs(backtests_dir, exist_ok=True)
                filename = f"rr_{self.params.rr}.csv"
                filepath = os.path.join(backtests_dir, filename)
        
        try:
            fieldnames = [
                'trade_id', 'symbol', 'order_side', 'state',
                'placed_candle', 'placed_datetime',
                'entry_price', 'entry_executed_price',
                'size', 'tp', 'sl',
                'open_candle', 'open_datetime',
                'close_candle', 'close_datetime',
                'exit_price', 'pnl', 
                # AI training
                'rsi_at_break', 'time_to_fill', 'relative_volume',
                'highest_excursion_from_breakout', 'atr_rel_excursion',
                'atr_breakout_wick', 'atr_sl_dist', 'atr_tp_dist',
            ]
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # Sort trades by open_candle to maintain chronological order
                sorted_trades = sorted(completed_trades, key=lambda x: x.get('open_candle', 0) or 0)
                
                trades_written = 0
                for trade in sorted_trades:
                    try:
                        # Convert OrderSide enum to string if needed
                        row = {}
                        for field in fieldnames:
                            value = trade.get(field)
                            # Handle OrderSide enum
                            if field == 'order_side' and isinstance(value, OrderSide):
                                row[field] = value.name
                            # Handle TradeState enum
                            elif field == 'state' and isinstance(value, TradeState):
                                row[field] = value.name
                            else:
                                row[field] = value
                        
                        writer.writerow(row)
                        trades_written += 1
                        
                    except Exception as e:
                        self.log(f"Error writing trade {trade.get('trade_id', 'unknown')} to CSV: {e}")
                        import traceback
                        self.log(traceback.format_exc())
                        continue
                
                # Calculate statistics
                winning_trades = [t for t in completed_trades if t.get('pnl', 0) > 0]
                losing_trades = [t for t in completed_trades if t.get('pnl', 0) < 0]
                total_trades = len(completed_trades)
                win_ratio = len(winning_trades) / total_trades if total_trades > 0 else 0
                total_tps = len(winning_trades)
                total_sls = len(losing_trades)
                
                # Safely calculate PnL sums
                def safe_pnl_sum(trades_list):
                    return sum([float(t.get('pnl', 0) or 0) for t in trades_list if t.get('pnl') is not None])
                
                total_pnl = safe_pnl_sum(completed_trades)
                total_win_pnl = safe_pnl_sum(winning_trades)
                total_loss_pnl = safe_pnl_sum(losing_trades)
                
                # Calculate equity curve for drawdown
                equity_curve = []
                equity = self.initial_cash
                for trade in sorted_trades:
                    equity_curve.append(equity)
                    pnl_val = trade.get('pnl')
                    if pnl_val is not None:
                        equity += pnl_val
                equity_curve.append(self.broker.getvalue())
                
                # Calculate max drawdown
                max_dd = 0.0
                peak = equity_curve[0] if equity_curve else self.initial_cash
                for value in equity_curve:
                    if value > peak:
                        peak = value
                    dd = (peak - value) / peak if peak > 0 else 0.0
                    if dd > max_dd:
                        max_dd = dd
                
                # Calculate Sharpe ratio
                import pandas as pd
                returns = pd.Series([t.get('pnl', 0) / self.initial_cash for t in completed_trades if t.get('pnl') is not None])
                sharpe_ratio = 0.0
                if len(returns) > 0 and returns.std() > 0:
                    sharpe_ratio = (returns.mean() / returns.std()) * (252 ** 0.5)
                
                # Write statistics footer
                final_equity = self.broker.getvalue()
                pnl_percentage = ((final_equity - self.initial_cash) / self.initial_cash * 100) if self.initial_cash > 0 else 0.0
                
                csvfile.write(f"\n")
                csvfile.write("-------- TRADE LOG --------\n")
                csvfile.write(f"# RR: {self.params.rr}\n")
                csvfile.write(f"# Win Ratio: {win_ratio:.2%}\n")
                csvfile.write(f"# TPs: {total_tps}\n")
                csvfile.write(f"# SLs: {total_sls}\n")
                csvfile.write(f"# Total Trades: {total_trades}\n")
                csvfile.write(f"# Total PnL: {total_pnl}\n")
                csvfile.write(f"# Total Win PnL: {total_win_pnl}\n")
                csvfile.write(f"# Total Loss PnL: {total_loss_pnl}\n")
                csvfile.write(f"# Init: {self.initial_cash}, Final: {final_equity}, Pnl%: {pnl_percentage:.2f}%\n")
                csvfile.write(f"# Max Drawdown: {max_dd:.2%}\n")
                csvfile.write(f"# Sharpe Ratio: {sharpe_ratio:.2f}\n")
                csvfile.write(f"#\n")
            
            self.log(f"Trades exported to: {filepath}")
            return filepath
            
        except Exception as e:
            self.log(f"Error exporting trades to CSV: {e}")
            import traceback
            self.log(traceback.format_exc())
            return None
    
    def log(self, txt, dt=None):
        if dt is None:
            dt = self.datas[0].datetime.datetime(0)
        print(f'{dt.strftime("%Y-%m-%d %H:%M")}: {txt}')

    def log_trade(self, state: TradeState, candle_index: int, order_side: OrderSide, additional_info: str = ''):
        emoji = ''
        if state == TradeState.RUNNING:
            emoji = 'RUNNING'
        elif state == TradeState.PENDING:
            emoji = 'PENDING'
        elif state == TradeState.CANCELED:
            emoji = 'CANCELLED'
        elif state == TradeState.SL_HIT:
            emoji = 'SL_HIT'
        elif state == TradeState.TP_HIT:
            emoji = 'TP_HIT'
        # if state == TradeState.RUNNING:
        #     emoji = '💹'
        # elif state == TradeState.PENDING:
        #     emoji = '➡️'
        # elif state == TradeState.CANCELED:
        #     emoji = '🚫'
        # elif state == TradeState.SL_HIT:
        #     emoji = '❌'
        # elif state == TradeState.TP_HIT:
        #     emoji = '🎯'
        
        self.log(f"{emoji}  {order_side.name}({candle_index}) {additional_info} Cash: {int(self.current_cash)}")
    
    def get_data_feed_index(self, data: bt.LineSeries) -> int:
        """
        Get the data feed index for a given data object.
        
        Args:
            data: Backtrader data feed object
        
        Returns:
            Index of the data feed, or 0 if not found
        
        Example:
            data_feed_index = self.get_data_feed_index(data)
            self.set_candle_data(data_feed_index=data_feed_index, order_placed=True)
        """
        data_indicators = self._get_data_indicators()
        for i, indicators_info in data_indicators.items():
            if indicators_info['data'] is data:
                return i
        return 0  # Default to first data feed if not found
    
    def set_candle_data(self, data_feed_index=0, **kwargs):
        """
        Set data for the current candle for a specific data feed.
        
        Args:
            data_feed_index: Index of the data feed (0 for first symbol, 1 for second, etc.)
            **kwargs: Key-value pairs to store for this candle
        
        Example:
            # For the first data feed (default)
            self.set_candle_data(order_placed=True, signal_type='breakout')
            
            # For a specific data feed (e.g., second symbol)
            self.set_candle_data(data_feed_index=1, order_placed=True, signal_type='breakout')
            
            # When placing an order on a specific data feed
            data_feed_index = self.get_data_feed_index(data)
            self.set_candle_data(data_feed_index=data_feed_index, order_placed=True)
        
        The data will be stored and can be extracted by plot.py for visualization.
        """
        candle_data = self._get_candle_data()
        if data_feed_index in candle_data and candle_data[data_feed_index]:
            candle_data[data_feed_index][-1].update(kwargs)
    
    def get_candle_data(self, key, data_feed_index=0, default=None):
        """
        Get data for the current candle for a specific data feed.
        
        Args:
            key: Key to retrieve
            data_feed_index: Index of the data feed (0 for first symbol, 1 for second, etc.)
            default: Default value if key not found
        
        Example:
            # For the first data feed (default)
            order_placed = self.get_candle_data('order_placed', default=False)
            
            # For a specific data feed
            order_placed = self.get_candle_data('order_placed', data_feed_index=1, default=False)
        """
        candle_data = self._get_candle_data()
        if data_feed_index in candle_data and candle_data[data_feed_index]:
            return candle_data[data_feed_index][-1].get(key, default)
        return default
    
    def _get_chart_markers(self):
        """Get chart_markers from cerebro or broker fallback."""
        cerebro = self._get_cerebro()
        if cerebro is not None and hasattr(cerebro, 'chart_markers'):
            return cerebro.chart_markers
        elif hasattr(self.broker, 'chart_markers'):
            return self.broker.chart_markers
        return {}
    
    def set_chart_marker(self, candle_index: int, price: float, data_feed_index: int = 0, marker_type: str = 'diamond', **kwargs):
        """
        Set a chart marker at a specific candle index and price level.
        This marker will be displayed on the plot.
        
        Args:
            candle_index: The candle index (0-based) where to show the marker
            price: The price level where to show the marker
            data_feed_index: Index of the data feed (0 for first symbol, 1 for second, etc.)
            marker_type: Type of marker ('diamond', 'circle', 'square', etc.) - defaults to 'diamond'
            **kwargs: Additional marker properties (color, size, etc.) for future extensibility
        
        Example:
            # Set a diamond at candle 100 at price 50000 for the first data feed
            self.set_chart_marker(100, 50000.0)
            
            # Set a diamond at current candle index at current close price
            self.set_chart_marker(self.candle_index, self.data.close[0])
            
            # Set a marker for a specific data feed
            self.set_chart_marker(150, 51000.0, data_feed_index=1)
            
            # Set a different marker type
            self.set_chart_marker(200, 52000.0, marker_type='circle', color='red')
        """
        cerebro = self._get_cerebro()
        marker_info = {
            'price': price,
            'type': marker_type,
            **kwargs  # Allow additional properties
        }
        
        if cerebro is not None:
            if not hasattr(cerebro, 'chart_markers'):
                cerebro.chart_markers = {}
            if data_feed_index not in cerebro.chart_markers:
                cerebro.chart_markers[data_feed_index] = {}
            cerebro.chart_markers[data_feed_index][candle_index] = marker_info
        else:
            # Fallback to broker if cerebro not available
            if not hasattr(self.broker, 'chart_markers'):
                self.broker.chart_markers = {}
            if data_feed_index not in self.broker.chart_markers:
                self.broker.chart_markers[data_feed_index] = {}
            self.broker.chart_markers[data_feed_index][candle_index] = marker_info
    
    def get_chart_marker(self, candle_index: int, data_feed_index: int = 0, default=None):
        """
        Get chart marker info for a specific candle index.
        
        Args:
            candle_index: The candle index (0-based) to retrieve marker for
            data_feed_index: Index of the data feed (0 for first symbol, 1 for second, etc.)
            default: Default value if marker not found
        
        Returns:
            Dict with marker info (price, type, etc.) or default if not found
        
        Example:
            # Get marker for candle 100
            marker = self.get_chart_marker(100)
            if marker:
                print(f"Price: {marker['price']}, Type: {marker['type']}")
        """
        chart_markers = self._get_chart_markers()
        if data_feed_index in chart_markers and candle_index in chart_markers[data_feed_index]:
            return chart_markers[data_feed_index][candle_index]
        return default
    
    def set_chart_data(self, data_type: ChartDataType, data_feed_index: int = 0, **kwargs):
        """
        Set chart data of a specific type. This is the new flexible method for sending
        data from strategies to charts, supporting various data types (markers, lines, zones).
        
        Args:
            data_type: Type of chart data (ChartDataType.MARKER, SUPPORT, RESISTANCE, EMA, ZONE)
            data_feed_index: Index of the data feed (0 for first symbol, 1 for second, etc.)
            **kwargs: Additional data based on type:
                - For MARKER: candle_index, price, marker_type
                - For SUPPORT/RESISTANCE: points (list of {time, value} dicts)
                - For EMA: points (list of {time, value} dicts)
                - For ZONE: points (list of {time, value} dicts)
        
        Example:
            # Set a retest order marker (replaces set_chart_marker)
            self.set_chart_data(ChartDataType.MARKER, 
                              candle_index=self.candle_index, 
                              price=current_price, 
                              marker_type=ChartMarkerType.RETEST_ORDER_PLACED)
            
            # Set support levels
            self.set_chart_data(ChartDataType.SUPPORT,
                              points=[{'time': 1234567890, 'value': 1.2500}])
            
            # Set EMA data
            self.set_chart_data(ChartDataType.EMA,
                              points=[{'time': t, 'value': v} for t, v in zip(times, ema_values)])
        """
        cerebro = self._get_cerebro()
        
        # Initialize chart_data structure if needed
        if cerebro is not None:
            if not hasattr(cerebro, 'chart_data'):
                cerebro.chart_data = {}
            if data_feed_index not in cerebro.chart_data:
                cerebro.chart_data[data_feed_index] = {}
        else:
            # Fallback to broker if cerebro not available
            if not hasattr(self.broker, 'chart_data'):
                self.broker.chart_data = {}
            if data_feed_index not in self.broker.chart_data:
                self.broker.chart_data[data_feed_index] = {}
        
        # Get the chart data container
        chart_data = cerebro.chart_data if cerebro is not None else self.broker.chart_data
        
        # Create or get the data container for this type
        if data_type.value not in chart_data[data_feed_index]:
            chart_data[data_feed_index][data_type.value] = ChartData(data_type, **kwargs)
        
        data_container = chart_data[data_feed_index][data_type.value]
        
        # Handle different data types
        if data_type == ChartDataType.MARKER:
            # Handle marker data (backward compatibility with set_chart_marker)
            candle_index = kwargs.get('candle_index')
            price = kwargs.get('price')
            marker_type = kwargs.get('marker_type', 'diamond')
            
            if candle_index is not None and price is not None:
                # Convert time from candle index to actual timestamp if available
                time_value = self._get_time_for_candle_index(candle_index, data_feed_index)
                data_container.add_point_at_time(
                    time=time_value,
                    value=price,
                    marker_type=marker_type,
                    candle_index=candle_index
                )
                
                # Also store in old chart_markers for backward compatibility
                self.set_chart_marker(candle_index, price, data_feed_index, marker_type)
        
        elif data_type in [ChartDataType.SUPPORT, ChartDataType.RESISTANCE, ChartDataType.EMA]:
            # Handle line/zone data
            points = kwargs.get('points', [])
            for point in points:
                if isinstance(point, dict) and 'time' in point and 'value' in point:
                    data_container.add_point_at_time(
                        time=point['time'],
                        value=point['value'],
                        **{k: v for k, v in point.items() if k not in ['time', 'value']}
                    )
    
    def _get_time_for_candle_index(self, candle_index: int, data_feed_index: int = 0) -> int:
        """
        Get the timestamp for a given candle index.
        This is a helper method for converting candle indices to timestamps.
        """
        try:
            data_indicators = self._get_data_indicators()
            if data_feed_index in data_indicators:
                data = data_indicators[data_feed_index]['data']
                if hasattr(data, 'datetime') and len(data.datetime) > candle_index:
                    return int(data.datetime[candle_index].timestamp())
        except (AttributeError, IndexError, ValueError):
            pass
        
        # Fallback: return candle_index as time (not ideal but prevents crashes)
        return candle_index
    
    def get_chart_data(self, data_type: ChartDataType, data_feed_index: int = 0) -> ChartData:
        """
        Get chart data for a specific type.
        
        Args:
            data_type: Type of chart data to retrieve
            data_feed_index: Index of the data feed
        
        Returns:
            ChartData object or empty ChartData if not found
        """
        cerebro = self._get_cerebro()
        chart_data = cerebro.chart_data if cerebro is not None else getattr(self.broker, 'chart_data', {})
        
        if (data_feed_index in chart_data and 
            data_type.value in chart_data[data_feed_index]):
            return chart_data[data_feed_index][data_type.value]
        
        # Return empty ChartData if not found
        return ChartData(data_type)
    
    def set_support_data(self, support_points: list, data_feed_index: int = 0, **kwargs):
        """
        Convenience method to set support level data.
        
        Args:
            support_points: List of support points [{'time': timestamp, 'value': price}, ...]
            data_feed_index: Index of the data feed
            **kwargs: Additional metadata
        """
        self.set_chart_data(ChartDataType.SUPPORT, data_feed_index, points=support_points, **kwargs)
    
    def set_resistance_data(self, resistance_points: list, data_feed_index: int = 0, **kwargs):
        """
        Convenience method to set resistance level data.
        
        Args:
            resistance_points: List of resistance points [{'time': timestamp, 'value': price}, ...]
            data_feed_index: Index of the data feed
            **kwargs: Additional metadata
        """
        self.set_chart_data(ChartDataType.RESISTANCE, data_feed_index, points=resistance_points, **kwargs)
    
    def set_ema_data(self, ema_points: list, data_feed_index: int = 0, **kwargs):
        """
        Convenience method to set EMA line data.
        
        Args:
            ema_points: List of EMA points [{'time': timestamp, 'value': ema_value}, ...]
            data_feed_index: Index of the data feed
            **kwargs: Additional metadata (e.g., period)
        """
        self.set_chart_data(ChartDataType.EMA, data_feed_index, points=ema_points, **kwargs)
    
    def sync_indicator_data_to_chart(self, data_feed_index: int = 0):
        """
        Automatically send current indicator data (support, resistance, EMA) to chart.
        This method should be called to keep charts in sync with current indicator values.
        
        Args:
            data_feed_index: Index of the data feed to sync
        """
        try:
            data_indicators = self._get_data_indicators()
            if data_feed_index not in data_indicators:
                return
            
            indicators = data_indicators[data_feed_index]
            data = indicators['data']
            
            # Get current time
            current_time = self._get_time_for_candle_index(self.candle_index, data_feed_index)
            
            # Send support and resistance from breakout indicator
            if 'breakout' in indicators:
                breakout = indicators['breakout']
                support_value = breakout.lines.support1[0] if len(breakout.lines.support1) > 0 else None
                resistance_value = breakout.lines.resistance1[0] if len(breakout.lines.resistance1) > 0 else None
                
                if support_value is not None and not math.isnan(support_value):
                    self.set_support_data(
                        support_points=[{'time': current_time, 'value': float(support_value)}],
                        data_feed_index=data_feed_index
                    )
                
                if resistance_value is not None and not math.isnan(resistance_value):
                    self.set_resistance_data(
                        resistance_points=[{'time': current_time, 'value': float(resistance_value)}],
                        data_feed_index=data_feed_index
                    )
            
            # Send EMA data
            if 'ema' in indicators:
                ema = indicators['ema']
                ema_value = ema[0] if len(ema) > 0 else None
                
                if ema_value is not None and not math.isnan(ema_value):
                    self.set_ema_data(
                        ema_points=[{'time': current_time, 'value': float(ema_value)}],
                        data_feed_index=data_feed_index,
                        period=getattr(ema, 'params', {}).get('period', 0)
                    )
                    
        except Exception as e:
            # Don't let chart data sync errors break the strategy
            pass
    
    def update_open_positions_summary(self):
        # Access data_indicators from cerebro (persists across strategy re-instantiation)
        data_indicators = self._get_data_indicators()
        for i, indicators_info in data_indicators.items():
            data = indicators_info['data']
            open_position = self.getposition(data)
            self.open_positions_summary[i] = open_position.size
    
    def log_to_repo(self, level: LogLevel, message: str, repository_name: str, date: str = None):
        self.logger.log(level, message, repository_name, date)