"""
MetaTrader 5 data feed for Backtrader.
Provides real-time and historical data from MT5.
"""

import backtrader as bt
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger
import MetaTrader5 as mt5
import time
import threading
from collections import deque
import sys
import os

# Import config - add src directory to path if needed
# File is in src/data/, config is in src/utils/
_current_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_current_dir)  # Go up from src/data/ to src/
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
from utils.config import Config


class MT5DataFeed:
    """
    MetaTrader 5 data feed wrapper for Backtrader.
    Provides real-time data fetching from MT5.
    """
    
    # MT5 timeframe mapping
    TIMEFRAME_MAP = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }
    
    def __init__(self, symbol: str, timeframe: str = 'H1', 
                 login: Optional[int] = None, password: Optional[str] = None,
                 server: Optional[str] = None, path: Optional[str] = None,
                 max_candles: Optional[int] = 1000):
        """
        Initialize MT5 data feed.
        
        Args:
            symbol: Trading symbol (e.g., 'AUDCHF', 'EURUSD')
            timeframe: Timeframe string ('M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1')
            login: MT5 account number (optional if already initialized)
            password: MT5 password (optional if already initialized)
            server: MT5 server name (optional if already initialized)
            path: Path to MT5 terminal (optional, auto-detected if not provided)
            max_candles: Maximum number of historical candles to load
        """
        self.symbol = symbol
        self.timeframe_str = timeframe.upper()
        self.max_candles = max_candles
        
        if self.timeframe_str not in self.TIMEFRAME_MAP:
            raise ValueError(f"Invalid timeframe: {timeframe}. Valid options: {list(self.TIMEFRAME_MAP.keys())}")
        
        self.timeframe = self.TIMEFRAME_MAP[self.timeframe_str]
        
        logger.info(f"Setting up MT5 data feed for {symbol} - Timeframe: {timeframe}")
        
        # Track if we initialized MT5 (to avoid shutting down if initialized elsewhere)
        # Try to initialize - if it fails with "already initialized" error, we're good
        try:
            # Only pass path parameter if it's provided (not None)
            if path:
                initialized = mt5.initialize(path=path)
            else:
                initialized = mt5.initialize()  # Let MT5 auto-detect the path
            if initialized:
                self._initialized_here = True
                logger.info(f"MT5 initialized successfully. Version: {mt5.version()}")
            else:
                error = mt5.last_error()
                if error[0] == 10004:  # Already initialized
                    self._initialized_here = False
                    logger.info("MT5 already initialized, reusing connection")
                else:
                    self._initialized_here = True
                    raise ConnectionError(f"MT5 initialization failed: {error}")
        except Exception as e:
            # Check if already initialized
            account_info = mt5.account_info()
            if account_info is not None:
                self._initialized_here = False
                logger.info("MT5 already initialized, reusing connection")
            else:
                raise
        
        # Login if credentials provided and not already logged in
        if login and password and server:
            account_info = mt5.account_info()
            if account_info is None or account_info.login != login:
                logger.info(f"Logging in to MT5 account: {login}")
                if not mt5.login(login, password=password, server=server):
                    error = mt5.last_error()
                    if self._initialized_here:
                        mt5.shutdown()
                    raise ConnectionError(f"MT5 login failed: {error}")
                logger.info("MT5 login successful")
            else:
                logger.info(f"Already logged in to account: {login}")
        
        # Verify symbol exists
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            if self._initialized_here:
                mt5.shutdown()
            raise ValueError(f"Symbol {symbol} not found in MT5")
        
        if not symbol_info.visible:
            logger.warning(f"Symbol {symbol} is not visible. Attempting to enable...")
            if not mt5.symbol_select(symbol, True):
                if self._initialized_here:
                    mt5.shutdown()
                raise ValueError(f"Failed to enable symbol {symbol}")
        
        logger.info(f"Symbol {symbol} verified. Bid: {symbol_info.bid}, Ask: {symbol_info.ask}")
        
        # Load historical data
        self.df = self._load_historical_data()
        
        if self.df.empty:
            mt5.shutdown()
            raise ValueError(f"No historical data found for {symbol}")
        
        logger.info(f"Loaded {len(self.df)} historical candles for {symbol}")
    
    def _load_historical_data(self) -> pd.DataFrame:
        """Load historical data from MT5."""
        # Use UTC time for MT5 (MT5 uses UTC)
        from datetime import timezone
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Calculate start date based on max_candles
        # Approximate: assume 1 candle per timeframe period
        if self.max_candles:
            if self.timeframe_str.startswith('M'):
                minutes = int(self.timeframe_str[1:])
                days_back = (self.max_candles * minutes) / (24 * 60) + 1
            elif self.timeframe_str.startswith('H'):
                hours = int(self.timeframe_str[1:])
                days_back = (self.max_candles * hours) / 24 + 1
            elif self.timeframe_str == 'D1':
                days_back = self.max_candles + 1
            else:
                days_back = 30  # Default
            
            from_date = now_utc - timedelta(days=int(days_back))
        else:
            from_date = now_utc - timedelta(days=30)  # Default 30 days
        
        to_date = now_utc
        
        logger.info(f"Fetching historical data from {from_date} to {to_date}")
        
        # Fetch rates
        rates = mt5.copy_rates_range(self.symbol, self.timeframe, from_date, to_date)
        
        if rates is None or len(rates) == 0:
            logger.warning("No rates returned, trying with more days back")
            from_date = now_utc - timedelta(days=365)  # Try 1 year
            rates = mt5.copy_rates_range(self.symbol, self.timeframe, from_date, to_date)
        
        # If still no data, try copy_rates_from_pos as fallback
        if rates is None or len(rates) == 0:
            logger.warning(f"Still no rates for {self.symbol}, trying copy_rates_from_pos")
            num_bars = self.max_candles if self.max_candles else 1000
            rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, num_bars)
        
        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            logger.error(f"No historical data found for {self.symbol}. MT5 error: {error}")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        # Rename columns to match Backtrader expectations
        df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'tick_volume': 'Volume'
        }, inplace=True)
        
        # Limit to max_candles if specified
        if self.max_candles and len(df) > self.max_candles:
            df = df.tail(self.max_candles)
        
        return df
    
    def get_backtrader_feed(self):
        """
        Get a Backtrader data feed configured for MT5 data.
        
        Returns:
            bt.feeds.PandasData: Configured Backtrader data feed
        """
        return bt.feeds.PandasData(
            dataname=self.df,
            datetime=None,  # Use the index (datetime)
            open='Open',
            high='High',
            low='Low',
            close='Close',
            volume='Volume',
            openinterest=-1  # No open interest data
        )
    
    def get_dataframe(self) -> pd.DataFrame:
        """Get the loaded dataframe."""
        return self.df
    
    def get_summary(self) -> dict:
        """Get a summary of the loaded data."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe_str,
            'total_rows': len(self.df),
            'date_range': {
                'start': self.df.index.min().strftime('%Y-%m-%d %H:%M:%S'),
                'end': self.df.index.max().strftime('%Y-%m-%d %H:%M:%S')
            },
            'price_range': {
                'min': self.df[['Open', 'High', 'Low', 'Close']].min().min(),
                'max': self.df[['Open', 'High', 'Low', 'Close']].max().max()
            },
            'volume_stats': {
                'min': self.df['Volume'].min(),
                'max': self.df['Volume'].max(),
                'mean': self.df['Volume'].mean()
            }
        }
    
    def shutdown(self):
        """Shutdown MT5 connection (only if we initialized it)."""
        if hasattr(self, '_initialized_here') and self._initialized_here:
            mt5.shutdown()
            logger.info("MT5 connection closed")
        else:
            logger.debug("Skipping MT5 shutdown (connection initialized elsewhere)")


class MT5LiveFeed(bt.feeds.DataBase):
    """
    Live MetaTrader 5 data feed for Backtrader.
    Extends DataBase to provide real-time bar updates without reloading historical data.
    """
    
    # MT5 timeframe mapping
    TIMEFRAME_MAP = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }
    
    params = (
        ('symbol', None),
        ('timeframe', 'H1'),
        ('max_candles', 1000),
        ('check_interval', 1.0),  # Seconds between checks for new bars
    )
    
    def __init__(self):
        import sys
        print(f"[MT5LiveFeed.__init__] Initializing for symbol={self.p.symbol}, timeframe={self.p.timeframe}", file=sys.stderr, flush=True)
        
        # Validate timeframe BEFORE calling super().__init__()
        timeframe_str = self.p.timeframe.upper()
        if timeframe_str not in self.TIMEFRAME_MAP:
            raise ValueError(f"Invalid timeframe: {self.p.timeframe}. Valid options: {list(self.TIMEFRAME_MAP.keys())}")
        
        # Map MT5 timeframe to backtrader timeframe and compression
        # Set these BEFORE calling super() so parent can access them
        # 
        # IMPORTANT: We fetch actual H1/H4/etc bars from MT5 (using mt5.TIMEFRAME_H1, etc.)
        # The bt_timeframe and compression below are ONLY for backtrader's internal representation.
        # Backtrader doesn't have a TimeFrame.Hours attribute, so it represents hours as
        # Minutes with compression. This is just how backtrader stores it internally - we're
        # still fetching and processing actual hourly bars from MT5, not aggregating minutes.
        if timeframe_str.startswith('M'):
            # Minutes: M1, M5, M15, M30
            bt_timeframe = bt.TimeFrame.Minutes
            compression = int(timeframe_str[1:])
        elif timeframe_str.startswith('H'):
            # Hours: H1, H4
            # Backtrader's internal representation: Minutes with compression
            # H1 bars from MT5 → represented as Minutes with compression=60 in backtrader
            # H4 bars from MT5 → represented as Minutes with compression=240 in backtrader
            bt_timeframe = bt.TimeFrame.Minutes
            compression = int(timeframe_str[1:]) * 60
        elif timeframe_str == 'D1':
            # Days
            bt_timeframe = bt.TimeFrame.Days
            compression = 1
        else:
            # Default to H1
            bt_timeframe = bt.TimeFrame.Minutes
            compression = 60
        
        # Call parent with timeframe and compression
        super(MT5LiveFeed, self).__init__()
        
        # Now set our attributes
        self.timeframe_str = timeframe_str
        # IMPORTANT: self.timeframe is the MT5 timeframe constant (e.g., mt5.TIMEFRAME_H1)
        # This is what we use when calling MT5 API functions to fetch actual H1/H4/etc bars
        self.timeframe = self.TIMEFRAME_MAP[timeframe_str]
        self.symbol = self.p.symbol
        
        # Set backtrader's internal timeframe attributes
        # Ensure _timeframe is an integer (TimeFrame constants are integers)
        self._timeframe = int(bt_timeframe) if hasattr(bt_timeframe, '__int__') else bt_timeframe
        self._compression = compression
        
        # Set dataname for backtrader identification
        self._dataname = f"{self.symbol}_{self.timeframe_str}"
        
        # Historical data storage
        self.historical_data = None
        self.current_bar_index = 0
        self.last_bar_time = None
        self.historical_fed = False  # Track if historical data has been fed
        
        # Live data queue
        self.live_bar_queue = deque()
        self.live_mode = False  # True when we've finished feeding historical data
        self.reset_flag = False  # Flag to reset for new run() call
        self.last_fed_bar = None  # Store last bar fed to backtrader for stale data
        self.fed_stale_this_run = False  # Track if we've fed stale data in this run()
        
        # Threading for live bar detection
        self.monitor_thread = None
        self.stop_monitoring = threading.Event()
        
        # MT5 initialization tracking
        self._initialized_here = False
    
    def start(self):
        """Called when the feed starts. Load historical data and start monitoring."""
        super(MT5LiveFeed, self).start()
        
        # If historical data is already loaded, skip reloading (happens on subsequent cerebro.run() calls)
        if self.historical_data is not None and len(self.historical_data) > 0:
            logger.debug(f"Historical data already loaded for {self.symbol}, skipping reload")
            return
        
        # Load historical data (only on first call)
        logger.info(f"Loading historical data for {self.symbol}...")
        self.historical_data = self._load_historical_data()
        
        if self.historical_data is None or len(self.historical_data) == 0:
            raise ValueError(f"No historical data found for {self.symbol}")
        
        # Set last bar time from historical data
        if len(self.historical_data) > 0:
            self.last_bar_time = self.historical_data.index[-1]
            logger.info(f"Loaded {len(self.historical_data)} historical bars. Last bar: {self.last_bar_time}")
        
        # Don't start monitoring thread here - it's started manually in main() after first run
    
    def stop(self):
        """Called when the feed stops. Clean up resources."""
        # Don't stop the monitoring thread here - we want it to keep running
        # backtrader calls stop() when cerebro.run() completes, but we want
        # the thread to keep monitoring for new bars
        logger.debug(f"stop() called for {self.symbol}, but keeping monitoring thread alive")
        super(MT5LiveFeed, self).stop()
    
    def getwriterinfo(self):
        """Override to provide proper timeframe info and avoid TypeError.
        
        The parent's getwriterinfo() calls TimeFrame.TName() which expects
        _timeframe to be an integer index, but it may be receiving a string.
        We override this to provide the info directly without calling TName().
        """
        # Build info dict directly to avoid parent's TName() call
        info = {}
        
        # Get dataname - use _dataname if set, otherwise try to construct it
        if hasattr(self, '_dataname'):
            info['dataname'] = self._dataname
        elif hasattr(self, 'symbol') and hasattr(self, 'timeframe_str'):
            info['dataname'] = f"{self.symbol}_{self.timeframe_str}"
        else:
            info['dataname'] = ''
        
        # Get name
        info['name'] = getattr(self, '_name', '')
        
        # Set Timeframe using our string representation
        if hasattr(self, 'timeframe_str'):
            info['Timeframe'] = self.timeframe_str
        elif hasattr(self, '_timeframe') and hasattr(self, '_compression'):
            # Map timeframe to string name
            try:
                if int(self._timeframe) == int(bt.TimeFrame.Minutes):
                    info['Timeframe'] = f"{self._compression}Min"
                # Note: Hours are represented as Minutes with compression in backtrader
                # So we don't check for TimeFrame.Hours here
                elif int(self._timeframe) == int(bt.TimeFrame.Days):
                    info['Timeframe'] = f"{self._compression}Day"
                else:
                    info['Timeframe'] = str(self._timeframe)
            except (ValueError, TypeError):
                # If conversion fails, just use string representation
                info['Timeframe'] = str(self._timeframe) if self._timeframe else 'Unknown'
        else:
            info['Timeframe'] = 'Unknown'
        
        return info
    
    
    def _load_historical_data(self) -> Optional[pd.DataFrame]:
        """Load historical data from MT5."""
        # Verify symbol is enabled
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            logger.error(f"Symbol {self.symbol} not found in MT5")
            return None
        
        if not symbol_info.visible:
            logger.warning(f"Symbol {self.symbol} is not visible. Attempting to enable...")
            if not mt5.symbol_select(self.symbol, True):
                logger.error(f"Failed to enable symbol {self.symbol}")
                return None
        
        # Use UTC time for MT5 (MT5 uses UTC)
        from datetime import timezone
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Calculate start date based on max_candles
        if self.p.max_candles:
            if self.timeframe_str.startswith('M'):
                minutes = int(self.timeframe_str[1:])
                days_back = (self.p.max_candles * minutes) / (24 * 60) + 1
            elif self.timeframe_str.startswith('H'):
                hours = int(self.timeframe_str[1:])
                days_back = (self.p.max_candles * hours) / 24 + 1
            elif self.timeframe_str == 'D1':
                days_back = self.p.max_candles + 1
            else:
                days_back = 30
            from_date = now_utc - timedelta(days=int(days_back))
        else:
            from_date = now_utc - timedelta(days=30)
        
        to_date = now_utc
        
        logger.debug(f"Fetching historical data for {self.symbol} from {from_date} to {to_date}")
        
        # Ensure symbol is selected before fetching (sometimes needed even if done earlier)
        if not mt5.symbol_select(self.symbol, True):
            logger.warning(f"Could not select symbol {self.symbol}, but continuing anyway")
        
        # Use copy_rates_from_pos as primary method to get the most recent complete bars
        # This ensures we get the latest bars available, not just bars up to now_utc (which excludes incomplete bars)
        num_bars = self.p.max_candles if self.p.max_candles else 1000
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, num_bars)
        
        # Fallback to copy_rates_range if copy_rates_from_pos fails
        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            logger.warning(f"copy_rates_from_pos failed for {self.symbol}, trying copy_rates_range. MT5 error: {error}")
            rates = mt5.copy_rates_range(self.symbol, self.timeframe, from_date, to_date)
            
            if rates is None or len(rates) == 0:
                error = mt5.last_error()
                logger.warning(f"No rates returned for {self.symbol} with date range, trying with more days back. MT5 error: {error}")
                from_date = now_utc - timedelta(days=365)
                rates = mt5.copy_rates_range(self.symbol, self.timeframe, from_date, to_date)
                
                if rates is None or len(rates) == 0:
                    error = mt5.last_error()
                    logger.warning(f"Still no rates for {self.symbol} with date range. MT5 error: {error}")
                    # Try copy_rates_from_pos with fewer bars as last resort
                    rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 100)
                    
                    if rates is None or len(rates) == 0:
                        logger.warning(f"Trying with just 10 bars...")
                        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 10)
        
        if rates is None or len(rates) == 0:
            error = mt5.last_error()
            logger.error(f"No historical data found for {self.symbol} after all attempts. MT5 error: {error}")
            # Try to get symbol info to see what's available
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info:
                logger.error(f"Symbol info: visible={symbol_info.visible}, select={symbol_info.select}")
            return None
        
        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        # Rename columns
        df.rename(columns={
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'tick_volume': 'Volume'
        }, inplace=True)
        
        # Limit to max_candles if specified
        if self.p.max_candles and len(df) > self.p.max_candles:
            df = df.tail(self.p.max_candles)
        
        return df
    
    def _monitor_new_bars(self):
        """Monitor for new bars in a separate thread."""
        # Use print() first to ensure we can see if thread is running
        print(f"[_monitor_new_bars] THREAD FUNCTION CALLED for {self.symbol}")
        
        # Log immediately to confirm thread is running
        try:
            logger.info(f"*** Monitor thread FUNCTION CALLED for {self.symbol} ***")
            print(f"[_monitor_new_bars] Logger works for {self.symbol}")
        except Exception as e:
            print(f"[_monitor_new_bars] CRITICAL: Cannot log! Error: {e}")
            import traceback
            traceback.print_exc()
            return
        
        try:
            print(f"[_monitor_new_bars] Thread STARTED for {self.symbol}. Waiting for historical data...")
            logger.info(f"*** Monitor thread STARTED for {self.symbol}. Waiting for historical data... ***")
            wait_count = 0
            max_wait = 1000  # Max 100 seconds wait for last_bar_time
            
            # Verify we have access to required attributes
            if not hasattr(self, 'symbol'):
                logger.error(f"Monitor thread: self.symbol not found!")
                return
            if not hasattr(self, 'timeframe'):
                logger.error(f"Monitor thread: self.timeframe not found!")
                return
            
            logger.info(f"Monitor thread for {self.symbol} entering main loop...")
            while not self.stop_monitoring.is_set():
                try:
                    # Wait for historical data to be loaded before monitoring
                    if self.last_bar_time is None:
                        wait_count += 1
                        if wait_count % 10 == 0:  # Log every second (10 * 0.1s)
                            logger.info(f"Monitor thread for {self.symbol} still waiting for last_bar_time to be set... (waited {wait_count * 0.1:.1f}s)")
                        if wait_count > max_wait:
                            logger.error(f"Monitor thread for {self.symbol} timed out waiting for last_bar_time!")
                            break
                        time.sleep(0.1)
                        continue
                    
                    # Log that we're monitoring (first time only)
                    if not hasattr(self, '_monitoring_started'):
                        logger.info(f"Monitor thread for {self.symbol} is now actively checking for new bars. Last bar time: {self.last_bar_time}")
                        self._monitoring_started = True
                    
                    # Fetch latest bars from MT5
                    rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 2)
                    
                    if rates is not None and len(rates) > 0:
                        # Convert to DataFrame
                        df_new = pd.DataFrame(rates)
                        df_new['time'] = pd.to_datetime(df_new['time'], unit='s')
                        df_new.set_index('time', inplace=True)
                        
                        # Rename columns
                        df_new.rename(columns={
                            'open': 'Open',
                            'high': 'High',
                            'low': 'Low',
                            'close': 'Close',
                            'tick_volume': 'Volume'
                        }, inplace=True)
                        
                        # Check if we have a new bar
                        latest_bar_time = df_new.index[-1]
                        
                        if self.last_bar_time is None or latest_bar_time > self.last_bar_time:
                            # New bar found!
                            latest_bar = df_new.iloc[-1]
                            
                            logger.info(f"*** NEW {self.timeframe_str} BAR DETECTED for {self.symbol} at {latest_bar_time}: "
                                      f"O={latest_bar['Open']:.5f}, H={latest_bar['High']:.5f}, "
                                      f"L={latest_bar['Low']:.5f}, C={latest_bar['Close']:.5f} ***")
                            
                            # Add to queue
                            self.live_bar_queue.append({
                                'datetime': latest_bar_time,
                                'open': float(latest_bar['Open']),
                                'high': float(latest_bar['High']),
                                'low': float(latest_bar['Low']),
                                'close': float(latest_bar['Close']),
                                'volume': int(latest_bar['Volume'])
                            })
                            
                            logger.info(f"Bar added to queue. Queue size for {self.symbol}: {len(self.live_bar_queue)}")
                            self.last_bar_time = latest_bar_time
                        else:
                            # Log when we check but no new bar (every 10 checks to avoid spam, only if debug logs enabled)
                            if not hasattr(self, '_check_count'):
                                self._check_count = 0
                            self._check_count += 1
                            if Config.show_debug_logs and self._check_count % 10 == 0:
                                logger.debug(f"Monitor check {self._check_count} for {self.symbol}: No new bar yet. Latest: {latest_bar_time}, Last processed: {self.last_bar_time}")
                    
                    # Sleep before next check
                    time.sleep(self.p.check_interval)
                    
                except Exception as e:
                    logger.error(f"*** ERROR in monitor thread loop for {self.symbol}: {e} ***")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    time.sleep(self.p.check_interval)
        except Exception as e:
            logger.error(f"*** FATAL ERROR in monitor thread for {self.symbol}: {e} ***")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            logger.warning(f"Monitor thread for {self.symbol} is exiting!")
    
    def _load(self):
        """
        Load the next bar. Called by backtrader repeatedly.
        Returns True if data was loaded, False if no more data available.
        """
        # Handle reset: if reset_flag is set, we're starting a new run() call
        # Skip historical data and only feed new live bars
        if self.reset_flag:
            self.reset_flag = False
            # Mark historical as fed, but don't set live_mode yet - only set it when we actually feed a live bar
            self.historical_fed = True
            self.live_mode = False  # Don't set to True until we actually feed a live bar
            logger.debug(f"Feed {self.symbol} reset for new run - skipping historical data, waiting for live bars")
        
        # First run: feed all historical bars
        if not self.historical_fed and self.historical_data is not None:
            # During historical backfill, live_mode should be False
            self.live_mode = False
            
            if self.current_bar_index < len(self.historical_data):
                # Feed next historical bar
                bar = self.historical_data.iloc[self.current_bar_index]
                
                # Store as last fed bar for stale data support
                self.last_fed_bar = {
                    'datetime': bar.name,
                    'open': float(bar['Open']),
                    'high': float(bar['High']),
                    'low': float(bar['Low']),
                    'close': float(bar['Close']),
                    'volume': int(bar['Volume'])
                }
                
                # Populate lines
                self.lines.datetime[0] = bt.date2num(bar.name)
                self.lines.open[0] = float(bar['Open'])
                self.lines.high[0] = float(bar['High'])
                self.lines.low[0] = float(bar['Low'])
                self.lines.close[0] = float(bar['Close'])
                self.lines.volume[0] = int(bar['Volume'])
                self.lines.openinterest[0] = 0
                
                self.current_bar_index += 1
                if self.current_bar_index % 100 == 0:
                    logger.debug(f"Fed {self.current_bar_index}/{len(self.historical_data)} historical bars for {self.symbol}")
                return True
            else:
                # Finished feeding historical data
                self.historical_fed = True
                # Don't set live_mode to True yet - only set it when we actually feed a live bar
                self.live_mode = False
                logger.info(f"Finished feeding historical data for {self.symbol}. Waiting for live bars...")
        
        # Live mode: check for new bars in queue
        # Only set live_mode to True when we actually feed a live bar
        # IMPORTANT: Only return True if we have a new bar - don't use stale data
        # This ensures we wait for all feeds to have bars before processing
        if self.historical_fed:
            if len(self.live_bar_queue) > 0:
                # Feed next live bar - NOW we're in live mode
                self.live_mode = True
                bar = self.live_bar_queue.popleft()
                self.last_fed_bar = bar  # Store for reference
                
                logger.info(f"*** FEEDING LIVE BAR to backtrader for {self.symbol} at {bar['datetime']}: "
                           f"O={bar['open']:.5f}, H={bar['high']:.5f}, "
                           f"L={bar['low']:.5f}, C={bar['close']:.5f} ***")
                
                # Populate lines
                self.lines.datetime[0] = bt.date2num(bar['datetime'])
                self.lines.open[0] = bar['open']
                self.lines.high[0] = bar['high']
                self.lines.low[0] = bar['low']
                self.lines.close[0] = bar['close']
                self.lines.volume[0] = bar['volume']
                self.lines.openinterest[0] = 0
                
                return True
            else:
                # No new bars - return False
                # Backtrader will wait until all feeds have bars before calling next()
                if Config.show_debug_logs:
                    logger.debug(f"No bars in queue for {self.symbol}, returning False")
                return False
        
        # No more data
        return False
    
    def prepare_for_next_run(self):
        """Call this before a new run() to prepare the feed."""
        # Set reset flag so we skip re-feeding historical data
        # Don't set live_mode to True yet - only set it when we actually feed a live bar
        self.reset_flag = True
        self.historical_fed = True
        self.live_mode = False  # Don't set to True until we actually feed a live bar

