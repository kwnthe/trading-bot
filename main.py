from datetime import datetime
import backtrader as bt
import sys
import os
import pandas as pd
import argparse
import time
import threading
from loguru import logger

# Add the src directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.config import Config, load_config
from src.data.csv_data_feed import CSVDataFeed
from indicators.TestIndicator import TestIndicator
from strategies.BreakRetestStrategy import BreakRetestStrategy
from src.observers.buy_sell_observer import BuySellObserver
from src.utils.backtesting import prepare_backtesting
from src.models.timeframe import Timeframe
from src.utils.plot import plotly_plot
from src.brokers.backtesting_broker import BacktestingBroker
from src.utils.strategy_utils.general_utils import convert_pips_to_price, convert_micropips_to_price

def backtesting(symbols: list[str], timeframe: Timeframe, start_date: datetime, end_date: datetime, max_candles: int = None, print_trades: bool = False, spread_pips: float = 0.0):
    """
    Run backtesting with optional spread simulation.
    
    Args:
        symbols: List of symbols to trade
        timeframe: Timeframe for trading
        start_date: Start date for backtesting
        end_date: End date for backtesting
        max_candles: Maximum number of candles to process
        print_trades: Whether to print trade details
        spread_pips: Spread in pips (default: 0.0 for no spread)
    """
    symbols_list = prepare_backtesting(symbols, timeframe, start_date, end_date)
    print(f"symbols_list: {symbols_list}")

    config = load_config()
    cerebro = bt.Cerebro(stdstats=False)
    
    # Initialize persistent state in cerebro (survives strategy re-instantiation)
    cerebro.data_indicators = {}
    cerebro.data_state = {}
    cerebro.broker = BacktestingBroker(spread_pips=spread_pips)
    
    data_feeds = []
    data_for_plotly = {}
    original_data_feeds = []  # Store references to original data feeds for resampling
    print(f"symbols_list: {symbols_list}")
    for config in symbols_list:
        csv_feed = CSVDataFeed(
            csv_file_path=config['csv_file'],
            max_candles=max_candles
        )
        data = csv_feed.get_backtrader_feed()
        data._name = config['symbol']  # Set name for identification
        data_for_plotly[config['symbol']] = data
        cerebro.adddata(data, name=config['symbol'])
        data_feeds.append({'feed': csv_feed, 'symbol': config['symbol']})
        original_data_feeds.append(data)  # Store reference for resampling
    
    # Resample all data feeds to daily timeframe for RSI calculation
    # Use replaydata instead of resampledata to avoid synchronization issues
    # replaydata replays data at a different timeframe without interfering with main feed synchronization
    # IMPORTANT: replaydata must be called BEFORE adding the strategy
    cerebro.daily_data_mapping = {}  # Maps original data index to daily data feed
    for i, (original_data, feed_info) in enumerate(zip(original_data_feeds, data_feeds)):
        # Use replaydata - it replays the data at daily timeframe without affecting synchronization
        # replaydata creates a separate data feed that replays at daily intervals
        daily_data = cerebro.replaydata(
            original_data,
            timeframe=bt.TimeFrame.Days,
            compression=1
        )
        daily_data._name = f"{feed_info['symbol']}_DAILY"  # Set name for identification
        cerebro.daily_data_mapping[i] = daily_data
        # Note: replaydata automatically adds the data feed to cerebro, so we don't need to call adddata
    
    # For backward compatibility, keep symbol variable (will use first symbol)
    symbol = symbols_list[0]['symbol']
    
    # Store backtest metadata for CSV export (after symbol is defined)
    cerebro.backtest_metadata = {
        'symbol': symbol,
        'timeframe': timeframe,
        'start_date': start_date,
        'end_date': end_date
    }

    cerebro.addobserver(BuySellObserver)
    
    # Print data summary for all feeds
    print(f"Data Summary:")
    for feed_info in data_feeds:
        summary = feed_info['feed'].get_summary()
        print(f"  {feed_info['symbol']}:")
        print(f"    CSV File: {summary['csv_file']}")
        print(f"    Total rows: {summary['total_rows']}")
        print(f"    Data range: {summary['date_range']['start']} to {summary['date_range']['end']}")
        print(f"    Price range: {summary['price_range']['min']:.5f} to {summary['price_range']['max']:.5f}")
    print()
    
    cerebro.addstrategy(BreakRetestStrategy, symbol=symbol, rr=Config.rr)
    cerebro.addindicator(TestIndicator)
    
    
    
    cerebro.broker.setcommission(commission=0.00008)
    cerebro.broker.set_checksubmit(False)  # Disable order size checks
    cerebro.broker.set_cash(Config.initial_equity)
    
    initial_cash = cerebro.broker.getcash()
    
    results = cerebro.run()
    strat = results[0]
    cerebro.strategy = strat
    final_equity = cerebro.broker.getvalue()
    
    pnl = final_equity - initial_cash
    pnl_percentage = (pnl / initial_cash) * 100
    
    # Calculate statistical metrics
    completed_trades = strat.completed_trades
    
    # Initialize default values for when there are no trades
    win_rate = 0.0
    avg_win = 0.0
    avg_loss = 0.0
    profit_factor = 0.0
    sharpe_ratio = 0.0
    
    print('=' * 80)
    print('BACKTEST RESULTS')
    print('=' * 80)
    print('Initial Cash: %.2f' % initial_cash)
    print('Final Equity: %.2f' % final_equity)
    print('PnL: %.2f' % pnl)
    print('PnL%%: %.2f%%' % pnl_percentage)
    print(f'TPs/SLs: {strat.counter["tp"]}/{strat.counter["sl"]}')
    
    if completed_trades:
        winning_trades = [t for t in completed_trades if t['pnl'] > 0]
        losing_trades = [t for t in completed_trades if t['pnl'] < 0]
        
        win_rate = len(winning_trades) / len(completed_trades) if completed_trades else 0
        max_win = max(t['pnl'] for t in winning_trades) if winning_trades else 0
        max_win_candle = max(t['placed_candle'] for t in winning_trades) if winning_trades else 0
        max_loss = min(t['pnl'] for t in losing_trades) if losing_trades else 0
        max_loss_candle = min(t['placed_candle'] for t in losing_trades) if losing_trades else 0
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        profit_factor = abs(sum(t['pnl'] for t in winning_trades) / sum(t['pnl'] for t in losing_trades)) if losing_trades and sum(t['pnl'] for t in losing_trades) != 0 else float('inf')
        
        
        # Calculate equity curve for drawdown
        # Sort by close_candle (when PnL is realized) instead of open_candle
        equity_curve = []
        current_equity = initial_cash
        for trade in sorted(completed_trades, key=lambda x: x.get('close_candle', x.get('open_candle', 0))):
            equity_curve.append(current_equity)
            if 'pnl' in trade:
                current_equity += trade['pnl']
        equity_curve.append(final_equity)
        
        # Calculate max drawdown
        max_dd = 0.0
        peak = initial_cash  # Start peak at initial cash
        max_dd_value = 0.0
        for value in equity_curve:
            if value > peak:
                peak = value
            dd = (peak - value) / peak if peak > 0 else 0.0
            dd_value = peak - value
            if dd > max_dd:
                max_dd = dd
                max_dd_value = dd_value
        
        # Calculate slippage statistics
        total_entry_slippage = sum([t.get('entry_slippage', 0) or 0 for t in completed_trades])
        total_close_slippage = sum([t.get('close_slippage', 0) or 0 for t in completed_trades])
        total_slippage_all = sum([t.get('total_slippage', 0) or 0 for t in completed_trades])
        avg_entry_slippage = total_entry_slippage / len(completed_trades) if completed_trades else 0
        avg_close_slippage = total_close_slippage / len(completed_trades) if completed_trades else 0
        
        print()
        print('=' * 80)
        print('STATISTICAL METRICS')
        print('=' * 80)
        print(f'Total Trades: {len(completed_trades)}')
        print(f'Win Rate: {win_rate:.2%}')
        print(f'Average Win: ${avg_win:.2f}')
        print(f'Average Loss: ${abs(avg_loss):.2f}')
        print(f'Profit Factor: {profit_factor:.2f}')
        print(f'Max Win: ${max_win:.2f} (Candle {max_win_candle})')
        print(f'Max Loss: ${max_loss:.2f} (Candle {max_loss_candle})')
        print(f'Max Drawdown: {max_dd:.2%} (${max_dd_value:.2f})')
        print(f'Sharpe Ratio: {sharpe_ratio:.2f}')
        print()
        print('EXECUTION COSTS')
        print('=' * 80)
        # Convert slippage to pips based on symbol type using utility functions
        symbol = cerebro.backtest_metadata.get('symbol', '')
        
        # Helper function to get pip value for a symbol (inverse of conversion functions)
        def get_pip_value(symbol: str) -> float:
            """
            Get pip value for a symbol (price per pip).
            Uses utility functions to avoid hardcoding values.
            """
            symbol_upper = symbol.upper()
            if symbol_upper.startswith("XAU") or symbol_upper.startswith("XAG"):
                # Metals: 1 pip = 0.001 (same as 1 micropip for metals)
                return convert_micropips_to_price(1.0, symbol)
            elif symbol_upper.endswith("JPY"):
                # JPY pairs: 1 pip = 0.01 (which is 10 micropips)
                # convert_micropips_to_price(10.0, symbol) = 10 * 0.001 = 0.01
                return convert_micropips_to_price(10.0, symbol)
            else:
                # Standard forex: 1 pip = 0.0001
                return convert_pips_to_price(1.0)
        
        pip_value = get_pip_value(symbol) if symbol else convert_pips_to_price(1.0)
        entry_slippage_pips = avg_entry_slippage / pip_value if pip_value > 0 else 0
        close_slippage_pips = avg_close_slippage / pip_value if pip_value > 0 else 0
        
        print(f'Avg Entry Slippage: {avg_entry_slippage:.5f} ({entry_slippage_pips:.2f} pips)')
        print(f'Avg Close Slippage: {avg_close_slippage:.5f} ({close_slippage_pips:.2f} pips)')
        print(f'Total Slippage Cost: ${total_slippage_all:.2f}')
        
        # Get execution stats from broker if using realistic execution
        if hasattr(cerebro.broker, 'get_execution_stats'):
            exec_stats = cerebro.broker.get_execution_stats()
            if exec_stats:
                print(f'Broker Execution Stats:')
                print(f'  Total Executions: {exec_stats["total_executions"]}')
                print(f'  Avg Slippage: {exec_stats["avg_slippage"]:.5f} ({exec_stats["avg_slippage"] / 0.0001:.2f} pips)')
                print(f'  Max Slippage: {exec_stats["max_slippage"]:.5f} ({exec_stats["max_slippage"] / 0.0001:.2f} pips)')
    else:
        print('No completed trades to analyze.')
    
    if print_trades:
        strat.print_trades()
    print(f"Trades verified: {strat.verify_trades()}")
    # Export trades to CSV (this is also automatically called in the stop() method)
    csv_file = strat.export_trades_to_csv()
    if csv_file:
        print(f"Trades exported to: {csv_file}")
    
    # Calculate Sharpe ratio if we have trades
    if completed_trades:
        returns = pd.Series([t['pnl'] / initial_cash for t in completed_trades])
        if len(returns) > 0 and returns.std() > 0:
            sharpe_ratio = (returns.mean() / returns.std()) * (252 ** 0.5)  # Annualized
    
    return {
        'cerebro': cerebro,
        'data': data_for_plotly,
        'stats': {
            'initial_cash': initial_cash,
            'final_equity': final_equity,
            'pnl': pnl,
            'pnl_percentage': pnl_percentage,
            'total_trades': len(completed_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
        }
    }


def live_trading():
    from src.brokers.mt5_broker import MT5Broker
    from src.data.mt5_data_feed import MT5LiveFeed
    
    config = load_config()
    
    # Validate MT5 credentials
    if not config.mt5_login or not config.mt5_password or not config.mt5_server or not config.mt5_symbol or not config.mt5_timeframe:
        logger.error("MT5 data misconfigured in .env file!")
        sys.exit(1)
    
    # Parse symbols (support comma-separated list)
    symbols = [s.strip() for s in config.mt5_symbol.split(',')]
    timeframe = config.mt5_timeframe or 'H1'
    
    logger.info("=" * 80)
    logger.info("STARTING LIVE TRADING WITH METATRADER 5")
    logger.info("=" * 80)
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Timeframe: {timeframe}")
    logger.info(f"Account: {config.mt5_login}")
    logger.info(f"Server: {config.mt5_server}")
    logger.info("=" * 80)
    
    # Initialize MT5 connection first
    import MetaTrader5 as mt5
    
    # Initialize MT5
    try:
        if config.mt5_path:
            initialized = mt5.initialize(path=config.mt5_path)
        else:
            initialized = mt5.initialize()
        
        if not initialized:
            error = mt5.last_error()
            logger.error(f"MT5 initialization failed: {error}")
            sys.exit(1)
        
        logger.info(f"MT5 initialized successfully. Version: {mt5.version()}")
    except Exception as e:
        logger.error(f"MT5 initialization error: {e}")
        sys.exit(1)
    
    # Login to MT5
    if not mt5.login(config.mt5_login, password=config.mt5_password, server=config.mt5_server):
        error = mt5.last_error()
        mt5.shutdown()
        logger.error(f"MT5 login failed: {error}")
        sys.exit(1)
    logger.info("MT5 login successful")
    
    # Verify symbols exist
    updated_symbols = []
    for i, symbol in enumerate(symbols):
        original_symbol = symbol
        symbol_info = mt5.symbol_info(symbol)
        
        # If symbol not found, try common variations
        if symbol_info is None:
            logger.warning(f"Symbol {symbol} not found, trying variations...")
            variations = [
                symbol + "#",  # Some brokers add #
                symbol + ".",  # Some brokers add .
                symbol.replace("USD", "#USD"),  # Some brokers use #USD
                symbol.replace("USD", ".USD"),  # Some brokers use .USD
            ]
            
            found_variation = None
            for variation in variations:
                test_info = mt5.symbol_info(variation)
                if test_info is not None:
                    logger.info(f"Found symbol variation: {variation} (instead of {symbol})")
                    symbol_info = test_info
                    symbol = variation  # Update symbol to use the found variation
                    found_variation = variation
                    break
            
            # If still not found, list available symbols
            if symbol_info is None:
                logger.error(f"Symbol {symbol} not found in MT5")
                logger.error(f"Last Error: {mt5.last_error()}")
                logger.info("Fetching available symbols from MT5...")
                
                # Get all available symbols
                all_symbols = mt5.symbols_get()
                if all_symbols:
                    logger.info(f"Found {len(all_symbols)} symbols available on this broker:")
                    # Filter symbols that might be related (contain part of the requested symbol)
                    base_symbol = symbol.replace("USD", "").replace("#", "").replace(".", "")
                    related_symbols = [s.name for s in all_symbols if base_symbol.upper() in s.name.upper()]
                    
                    if related_symbols:
                        logger.info(f"Symbols containing '{base_symbol}':")
                        for s in sorted(related_symbols)[:20]:  # Show first 20 matches
                            logger.info(f"  - {s}")
                    else:
                        logger.info("No similar symbols found. Showing first 50 available symbols:")
                        for s in sorted([s.name for s in all_symbols])[:50]:
                            logger.info(f"  - {s}")
                else:
                    logger.error("Could not retrieve symbol list from MT5")
                
                mt5.shutdown()
                logger.error(f"\nPlease check your symbol name. The symbol '{symbol}' is not available on broker '{config.mt5_server}'.")
                logger.error("You may need to:")
                logger.error("  1. Check the symbol name in MT5 Market Watch")
                logger.error("  2. Add the symbol to Market Watch in MT5")
                logger.error("  3. Use a different symbol name if your broker uses a different naming convention")
                sys.exit(1)
        
        if not symbol_info.visible:
            logger.warning(f"Symbol {symbol} is not visible. Attempting to enable...")
            if not mt5.symbol_select(symbol, True):
                mt5.shutdown()
                logger.error(f"Failed to enable symbol {symbol}")
                sys.exit(1)
        logger.info(f"Symbol {symbol} verified. Bid: {symbol_info.bid}, Ask: {symbol_info.ask}")
        
        # Store the verified symbol (may be a variation if original wasn't found)
        updated_symbols.append(symbol)
    
    # Update symbols list with any variations that were found
    symbols = updated_symbols
    
    # Create Cerebro instance
    cerebro = bt.Cerebro(stdstats=False)
    # Initialize persistent state in cerebro (survives strategy re-instantiation)
    cerebro.data_indicators = {}
    cerebro.data_state = {}
    
    # Add live data feeds for all symbols
    live_feeds = []
    for i, symbol in enumerate(symbols):
        try:
            logger.info(f"Initializing live data feed for {symbol}...")
            live_feed = MT5LiveFeed(
                symbol=symbol,
                timeframe=timeframe,
                max_candles=1000,
                check_interval=1.0  # Check for new bars every second
            )
            live_feed._name = symbol  # Set name for identification
            
            # Configure synchronization: first feed is master, others follow
            # This ensures next() is called whenever the master feed has a new bar
            if i == 0:
                # First feed is the master - add it normally
                cerebro.adddata(live_feed, name=symbol)
            else:
                # Other feeds are slaves - they will use stale data if no new bar available
                # This allows next() to be called even if not all feeds have new bars
                cerebro.adddata(live_feed, name=symbol)
            
            live_feeds.append(live_feed)
            logger.info(f"✓ {symbol} live feed initialized")
        except Exception as e:
            logger.error(f"Failed to initialize live feed for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    if not live_feeds:
        logger.error("No live feeds could be initialized!")
        mt5.shutdown()
        sys.exit(1)
    
    # For backward compatibility, use first symbol for strategy
    symbol = symbols[0]
    
    # Add strategy (strategy will handle multiple data feeds automatically)
    cerebro.addstrategy(BreakRetestStrategy, symbol=symbol, rr=config.rr)
    cerebro.addindicator(TestIndicator)
    
    # Set MT5 broker (supports multiple symbols)
    cerebro.broker = MT5Broker(symbols=symbols)
    cerebro.broker.setcommission(commission=0.00008)
    
    # Get initial account info (mt5 already imported above)
    account_info = mt5.account_info()
    if account_info:
        initial_balance = float(account_info.balance)
        initial_equity = float(account_info.equity)
        logger.info(f"Account Balance: ${initial_balance:.2f}")
        logger.info(f"Account Equity: ${initial_equity:.2f}")
        logger.info(f"Leverage: 1:{account_info.leverage}")
        
        # Set broker cash to match MT5 account balance
        cerebro.broker.set_cash(initial_balance)
        logger.info(f"Broker cash set to: ${initial_balance:.2f}")
    else:
        logger.error("Could not retrieve account info from MT5!")
        logger.error("Please ensure MT5 is connected and logged in.")
        # Shutdown MT5 if any feed initialized it
        try:
            mt5.shutdown()
        except:
            pass
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info("STARTING LIVE TRADING...")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 80)
    
    try:
        # Run cerebro - this will process historical data first
        # The MT5LiveFeed will handle feeding historical bars, then switch to live mode
        logger.info("Starting backtrader engine...")
        logger.info("Processing historical data first, then switching to live mode...")
        
        # First run: process all historical data
        # This will initialize the strategy with historical context
        # NOTE: backtrader calls start() on data feeds during cerebro.run()
        logger.info("Processing historical data...")
        logger.info("This will call strategy.next() for each historical bar.")
        logger.info("You should see 'PLACING ORDER' prints if next() is being called.")
        logger.info("NOTE: Data feed start() method will be called by backtrader during run()")
        
        results = cerebro.run()
        strat = results[0]
        logger.info(f"Historical data processing complete. Processed {len(strat.data)} bars.")
        
        # Check if all feeds have finished historical data
        all_live = all(feed.live_mode for feed in live_feeds)
        if not all_live:
            logger.warning("Not all feeds have entered live mode. Some may still be processing historical data.")
        
        logger.info("Historical data processed. Entering live trading mode...")
        logger.info("Starting monitoring threads manually...")
        
        # Start monitoring threads manually (more reliable than relying on start() method)
        for feed in live_feeds:
            try:
                # Stop any existing thread
                if feed.monitor_thread and feed.monitor_thread.is_alive():
                    feed.stop_monitoring.set()
                    feed.monitor_thread.join(timeout=1.0)
                
                # Start new monitoring thread
                feed.stop_monitoring.clear()
                feed.monitor_thread = threading.Thread(
                    target=feed._monitor_new_bars, 
                    daemon=True, 
                    name=f"MT5Monitor-{feed.symbol}"
                )
                feed.monitor_thread.start()
                logger.info(f"Started monitoring thread for {feed.symbol}")
                
                # Give it a moment to start
                time.sleep(0.2)
                
                if feed.monitor_thread.is_alive():
                    logger.info(f"✓ Monitoring thread for {feed.symbol} is running")
                else:
                    logger.error(f"✗ Monitoring thread for {feed.symbol} died immediately!")
            except Exception as e:
                logger.error(f"Failed to start monitoring thread for {feed.symbol}: {e}")
                import traceback
                traceback.print_exc()
        
        logger.info("Waiting for new bars and processing them as they arrive...")
        
        # Live trading loop: continuously check for new bars and process them
        # We use a loop because cerebro.run() exits when all feeds return False
        # Each iteration processes any new bars that arrived since last run
        iteration = 0
        last_status_log = time.time()
        
        while True:
            try:
                iteration += 1
                
                # Check if any feed has new bars in queue
                has_new_bars = any(len(feed.live_bar_queue) > 0 for feed in live_feeds)
                queue_sizes = {feed.symbol: len(feed.live_bar_queue) for feed in live_feeds}
                
                # Log queue status every 10 iterations for debugging (only if debug logs enabled)
                if Config.show_debug_logs and iteration % 10 == 0:
                    logger.debug(f"Live trading loop iteration {iteration}. Queue sizes: {queue_sizes}")
                
                if has_new_bars:
                    # Check if all feeds have bars for the same timestamp (at the front of their queues)
                    # IMPORTANT: Only proceed when all feeds have bars for the SAME timestamp
                    all_have_bars = all(len(feed.live_bar_queue) > 0 for feed in live_feeds)
                    
                    if all_have_bars:
                        # All feeds have bars - check if they're for the same timestamp
                        bar_times = []
                        bar_info = {}
                        for feed in live_feeds:
                            if len(feed.live_bar_queue) > 0:
                                # Peek at the first bar without removing it
                                bar = feed.live_bar_queue[0]
                                bar_times.append(bar['datetime'])
                                bar_info[feed.symbol] = bar['datetime']
                        
                        # If all bars are for the same timestamp, we're ready to process
                        if len(set(bar_times)) == 1:
                            logger.info(f"All feeds have bars for timestamp {bar_times[0]}, proceeding...")
                        else:
                            # Bars are for different timestamps - log and skip
                            queue_sizes = {feed.symbol: len(feed.live_bar_queue) for feed in live_feeds}
                            logger.warning(f"*** SKIPPING: Bars are for different timestamps. Queue sizes: {queue_sizes}, Timestamps: {bar_info}. Waiting... ***")
                            time.sleep(0.5)  # Wait a bit before checking again
                            continue
                    else:
                        # Not all feeds have bars yet - skip
                        queue_sizes = {feed.symbol: len(feed.live_bar_queue) for feed in live_feeds}
                        missing_feeds = [feed.symbol for feed in live_feeds if len(feed.live_bar_queue) == 0]
                        logger.warning(f"*** SKIPPING: Not all feeds have bars yet. Queue sizes: {queue_sizes}. Missing: {missing_feeds}. Waiting... ***")
                        time.sleep(0.5)  # Wait a bit before checking again
                        continue
                    
                    # Prepare feeds and run cerebro to process them
                    # Note: Strategy state will reset, but broker state (positions, cash) is preserved
                    queue_sizes = {feed.symbol: len(feed.live_bar_queue) for feed in live_feeds}
                    logger.info(f"*** PROCESSING NEW BARS (iteration {iteration}). Queue sizes: {queue_sizes} ***")
                    
                    # Ensure monitoring threads are still running before processing
                    for feed in live_feeds:
                        if feed.monitor_thread and not feed.monitor_thread.is_alive():
                            logger.warning(f"Monitoring thread for {feed.symbol} died! Restarting...")
                            feed.stop_monitoring.clear()
                            feed.monitor_thread = threading.Thread(
                                target=feed._monitor_new_bars, 
                                daemon=True, 
                                name=f"MT5Monitor-{feed.symbol}"
                            )
                            feed.monitor_thread.start()
                            time.sleep(0.1)
                    
                    for feed in live_feeds:
                        queue_size_before = len(feed.live_bar_queue)
                        feed.prepare_for_next_run()
                        logger.info(f"Prepared feed {feed.symbol} for next run. Queue size: {queue_size_before}")
                    
                    logger.info("Calling cerebro.run() to process new bars...")
                    results = cerebro.run()
                    strat = results[0]
                    
                    # Verify threads are still alive after run
                    for feed in live_feeds:
                        if feed.monitor_thread:
                            if not feed.monitor_thread.is_alive():
                                logger.warning(f"Monitoring thread for {feed.symbol} died after run()! Restarting...")
                                feed.stop_monitoring.clear()
                                feed.monitor_thread = threading.Thread(
                                    target=feed._monitor_new_bars, 
                                    daemon=True, 
                                    name=f"MT5Monitor-{feed.symbol}"
                                )
                                feed.monitor_thread.start()
                    
                    logger.info(f"*** Finished processing bars. Strategy next() should have been called. ***")
                else:
                    # No new bars yet - wait a bit before checking again
                    time.sleep(0.5)  # Check every 0.5 seconds
                
                # Log status periodically (every 60 seconds)
                current_time = time.time()
                if current_time - last_status_log >= 60:
                    account_info = mt5.account_info()
                    if account_info:
                        current_equity = float(account_info.equity)
                        pnl = current_equity - initial_equity
                        logger.info(f"Status check - Equity: ${current_equity:.2f}, PnL: ${pnl:.2f}")
                        if hasattr(strat, 'completed_trades'):
                            logger.info(f"Completed Trades: {len(strat.completed_trades)}")
                    last_status_log = current_time
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"Error in live trading loop: {e}")
                import traceback
                traceback.print_exc()
                # Wait a bit before retrying
                time.sleep(5)
        
    except KeyboardInterrupt:
        logger.info("\nStopping live trading...")
    except Exception as e:
        logger.error(f"Error during live trading: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Get final account info
        account_info = mt5.account_info()
        if account_info:
            final_balance = account_info.balance
            final_equity = account_info.equity
            pnl = final_equity - initial_equity
            pnl_percentage = (pnl / initial_equity) * 100 if initial_equity > 0 else 0
            
            logger.info("=" * 80)
            logger.info("LIVE TRADING SESSION ENDED")
            logger.info("=" * 80)
            logger.info(f"Initial Equity: ${initial_equity:.2f}")
            logger.info(f"Final Equity: ${final_equity:.2f}")
            logger.info(f"PnL: ${pnl:.2f}")
            logger.info(f"PnL%: {pnl_percentage:.2f}%")
            
            if 'strat' in locals() and hasattr(strat, 'completed_trades'):
                logger.info(f"Completed Trades: {len(strat.completed_trades)}")
        
        # Export trades
        if 'strat' in locals() and hasattr(strat, 'export_trades_to_csv'):
            csv_file = strat.export_trades_to_csv()
            if csv_file:
                logger.info(f"Trades exported to: {csv_file}")
        
        # Stop all live feeds
        for feed in live_feeds:
            try:
                feed.stop()
            except:
                pass
        
        # Shutdown MT5 connection
        try:
            mt5.shutdown()
            logger.info("MT5 connection closed")
        except:
            pass

if __name__ == '__main__':
    def parse_date(s: str) -> datetime:
        for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                pass
        raise argparse.ArgumentTypeError(
            'Date must be YYYY-MM-DD or YYYY-MM-DD HH:MM:SS'
        )
    parser = argparse.ArgumentParser(description='Trading Bot - Backtest or Live Trading')
    parser.add_argument('-m', '--metatrader', action='store_true',
                        help='Start live trading with MetaTrader 5')
    parser.add_argument('-s', '--symbols', nargs='+', default=['GBPAUD'],
                        help='Symbols to trade')
    parser.add_argument('-t', '--timeframe', type=Timeframe.from_value, default=Timeframe.H1,
                        help='Timeframe to trade (M1, M5, M15, M30, H1, H4, D1)')
    parser.add_argument('-st', '--start-date', type=parse_date, default=datetime(2025, 1, 1, 0, 0, 0),
                        help='Start date for backtesting')
    parser.add_argument('-en', '--end-date', type=parse_date, default=datetime(2025, 12, 15, 0, 0, 0),
                        help='End date for backtesting')
    parser.add_argument('-ch', '--chart', action='store_true',
                        help='Show chart')
    parser.add_argument('-mc', '--max-candles', type=int, help='Max Candles (backtesting only)', default=None)
    parser.add_argument('--spread-pips', type=float, default=0.0,
                        help='Spread in pips for backtesting (default: 0.0 for no spread)')
    
    
    
    args = parser.parse_args()
    
        
    if args.metatrader:
        live_trading()
    else:
        results = backtesting(args.symbols, args.timeframe, args.start_date, args.end_date, max_candles=args.max_candles, spread_pips=args.spread_pips)
        cerebro = results['cerebro']
        data = results['data']
        stats = results['stats']
        if args.chart:
            for symbol_index, (symbol, pair_data) in enumerate(data.items()):
                plotly_plot(cerebro, pair_data, symbol, symbol_index=symbol_index, height=700)

    
