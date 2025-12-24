import backtrader as bt
import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from indicators import BreakoutIndicator
from indicators import BreakRetestIndicator
from models.candlestick import Candlestick
from src.models.order import OrderSide, OrderType, TradeState
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
        self.candle_index = -1
        self.current_candle = None
        self.open_positions_summary = {} # Tracks the current position on each data feed
        self.trades = {}
        self.logger = StrategyLogger.get_logger()
        self.rsi = bt.indicators.RSI(
            self.data.close,
            period=14
        )

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
            
            # Initialize indicators for all data feeds
            for i, data in enumerate(self.datas):
                symbol = getattr(data, '_name', self.params.symbol or f'SYMBOL_{i}')
                # Only initialize if not already present (to preserve state across runs)
                if i not in cerebro.data_indicators:
                    cerebro.data_indicators[i] = {
                        'breakout': BreakoutIndicator(data, symbol=symbol),
                        'break_retest': BreakRetestIndicator(data, symbol=symbol),
                        'symbol': symbol,
                        'data': data
                    }
                if i not in cerebro.data_state:
                    cerebro.data_state[i] = {
                        'just_broke_out': None,
                        'breakout_trend': None,
                        'support': None,
                        'resistance': None,
                    }
            
            # For backward compatibility, keep main indicators pointing to first data feed
            self.breakout_indicator = cerebro.data_indicators[0]['breakout']
            self.break_retest_indicator = cerebro.data_indicators[0]['break_retest']
        
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
    
    def next(self):
        self.candle_index += 1
        self.update_open_positions_summary()
        
        # Get cerebro instance
        cerebro = self._get_cerebro()
        data_indicators = self._get_data_indicators()
        data_state = self._get_data_state()
        
        # Process all data feeds and update state for each
        for i, indicators_info in data_indicators.items():
            data = indicators_info['data']
            breakout_ind = indicators_info['breakout']
            
            # Update state for this data feed
            just_broke_out, breakout_trend = breakout_ind.just_broke_out()
            support = breakout_ind.lines.support1[0]
            resistance = breakout_ind.lines.resistance1[0]
            
            # Store in cerebro if available, otherwise broker
            if cerebro is not None:
                if not hasattr(cerebro, 'data_state'):
                    cerebro.data_state = {}
                cerebro.data_state[i] = cerebro.data_state.get(i, {})
                cerebro.data_state[i]['just_broke_out'] = just_broke_out
                cerebro.data_state[i]['breakout_trend'] = breakout_trend
                cerebro.data_state[i]['support'] = support
                cerebro.data_state[i]['resistance'] = resistance
            else:
                if not hasattr(self.broker, 'data_state'):
                    self.broker.data_state = {}
                self.broker.data_state[i] = self.broker.data_state.get(i, {})
                self.broker.data_state[i]['just_broke_out'] = just_broke_out
                self.broker.data_state[i]['breakout_trend'] = breakout_trend
                self.broker.data_state[i]['support'] = support
                self.broker.data_state[i]['resistance'] = resistance
        
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
                    filename = generate_csv_filename(symbol, timeframe, start_date, end_date)
                    # Modify path to use data/backtests directory
                    filename = Path(filename)
                    filename = filename.name  # Get just the filename
                else:
                    filename = f"rr_{self.params.rr}.csv"
            else:
                filename = f"rr_{self.params.rr}.csv"
        
        # Ensure we're in the project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # Create data/backtests directory if it doesn't exist
        backtests_dir = os.path.join(project_root, 'data', 'backtests')
        os.makedirs(backtests_dir, exist_ok=True)
        filepath = os.path.join(backtests_dir, filename)
        
        try:
            # Define CSV columns - only fields that are already tracked
            fieldnames = [
                'trade_id', 'symbol', 'order_side', 'state',
                'placed_candle', 'placed_datetime',
                'entry_price', 'entry_executed_price',
                'size', 'tp', 'sl',
                'open_candle', 'open_datetime',
                'close_candle', 'close_datetime',
                'exit_price', 'pnl', 'close_reason'
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
    
    def update_open_positions_summary(self):
        # Access data_indicators from cerebro (persists across strategy re-instantiation)
        data_indicators = self._get_data_indicators()
        for i, indicators_info in data_indicators.items():
            data = indicators_info['data']
            open_position = self.getposition(data)
            self.open_positions_summary[i] = open_position.size
    
    def log_to_repo(self, level: LogLevel, message: str, repository_name: str, date: str = None):
        self.logger.log(level, message, repository_name, date)