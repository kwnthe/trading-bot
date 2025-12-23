"""
Polygon.io data feed for Backtrader.
"""

import backtrader as bt
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger


class PolygonDataFeed:
    """
    Polygon.io data feed wrapper for Backtrader.
    Provides real-time data fetching and validation functionality.
    """
    
    def __init__(self, symbol: str, start_date: str, end_date: str, interval: str = "1h", 
                 api_key: str = "fBKVS8Xa3HaObC0pOFwxQmbjJ47dTbZW", max_candles: Optional[int] = None):
        """
        Initialize Polygon.io data feed.
        
        Args:
            symbol: Trading symbol (e.g., 'EURUSD' for EUR/USD)
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            interval: Data interval ('1m', '5m', '15m', '30m', '1h', '1d')
            api_key: Polygon.io API key
            max_candles: Maximum number of candlesticks to keep (None for no limit)
        """
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.interval = interval
        self.api_key = api_key
        self.max_candles = max_candles
        
        logger.info(f"Fetching Polygon.io data for {symbol} - Period: {start_date} to {end_date}, Interval: {interval}")
        
        # Fetch data from Polygon.io
        try:
            self.df = self._fetch_data()
            
            if self.df.empty:
                raise ValueError(f"No data returned for symbol {symbol}")
            
            logger.info(f"Loaded {len(self.df)} rows from Polygon.io")
            logger.info(f"Date range: {self.df.index.min()} to {self.df.index.max()}")
            
            # Validate required columns
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing_columns = [col for col in required_columns if col not in self.df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Validate data types and ranges
            price_columns = ['Open', 'High', 'Low', 'Close']
            for col in price_columns:
                if self.df[col].dtype not in ['float64', 'int64']:
                    logger.warning(f"Converting {col} to float64")
                    self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
                
                # Check for negative prices
                if (self.df[col] <= 0).any():
                    logger.warning(f"Found non-positive values in {col} column")
            
            # Validate OHLC relationships
            invalid_ohlc = (
                (self.df['High'] < self.df['Low']) |
                (self.df['High'] < self.df['Open']) |
                (self.df['High'] < self.df['Close']) |
                (self.df['Low'] > self.df['Open']) |
                (self.df['Low'] > self.df['Close'])
            )
            
            if invalid_ohlc.any():
                logger.warning(f"Found {invalid_ohlc.sum()} rows with invalid OHLC relationships")
            
            # Fill any NaN values
            self.df = self.df.ffill().bfill()
            
            # Limit the number of candlesticks if specified
            if self.max_candles is not None and len(self.df) > self.max_candles:
                logger.info(f"Limiting data to last {self.max_candles} candlesticks (from {len(self.df)} total)")
                self.df = self.df.tail(self.max_candles)
            
        except Exception as e:
            logger.error(f"Error fetching Polygon.io data: {e}")
            raise
    
    def _format_symbol_for_polygon(self, symbol: str) -> str:
        """Format symbol for Polygon.io API (forex pairs need C: prefix)."""
        forex_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD', 'AUDCHF']
        if symbol.upper() in forex_pairs:
            return f"C:{symbol.upper()}"
        return symbol.upper()
    
    def _fetch_data(self) -> pd.DataFrame:
        """Fetch data from Polygon.io API."""
        formatted_symbol = self._format_symbol_for_polygon(self.symbol)
        logger.info(f"Using formatted symbol: {formatted_symbol}")
        
        # Map interval to Polygon API format
        interval_map = {
            '1m': 'minute',
            '5m': 'minute', 
            '15m': 'minute',
            '30m': 'minute',
            '1h': 'hour',
            '1d': 'day',
            '1wk': 'week',
            '1mo': 'month'
        }
        
        polygon_interval = interval_map.get(self.interval, 'hour')
        url = f"https://api.polygon.io/v2/aggs/ticker/{formatted_symbol}/range/1/{polygon_interval}/{self.start_date}/{self.end_date}"
        params = {
            "apikey": self.api_key,
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000  # High limit to ensure we get all data
        }
        
        logger.info(f"Fetching {self.interval} data for {self.symbol} from {self.start_date} to {self.end_date}")
        response = requests.get(url, params=params)
        
        if response.status_code != 200:
            error_msg = f"API request failed with status code: {response.status_code}"
            try:
                error_data = response.json()
                error_msg += f" - Error: {error_data}"
            except:
                error_msg += f" - Response: {response.text}"
            raise ValueError(error_msg)
        
        data = response.json()
        
        if data.get("status") != "OK" or not data.get("results"):
            raise ValueError(f"No data found or API returned an error: {data}")
        
        results = data["results"]
        logger.info(f"Found {len(results)} bars for {self.symbol}")
        
        # Convert data to pandas DataFrame
        df_data = []
        for bar in results:
            timestamp = datetime.fromtimestamp(bar["t"] / 1000)  # Convert from milliseconds
            df_data.append({
                'timestamp': timestamp,
                'datetime': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'open': bar['o'],
                'high': bar['h'],
                'low': bar['l'],
                'close': bar['c'],
                'volume': bar['v']
            })
        
        # Create DataFrame
        df = pd.DataFrame(df_data)
        
        # Set timestamp as index and rename columns to match Backtrader expectations
        df.set_index('timestamp', inplace=True)
        df.rename(columns={
            'open': 'Open',
            'high': 'High', 
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        }, inplace=True)
        
        return df
    
    def get_backtrader_feed(self):
        """
        Get a Backtrader data feed configured for Polygon.io data.
        
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
            'start_date': self.start_date,
            'end_date': self.end_date,
            'interval': self.interval,
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
