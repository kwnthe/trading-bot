"""
Yahoo Finance data feed for Backtrader.
"""

import backtrader as bt
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from loguru import logger


class YahooDataFeed:
    """
    Yahoo Finance data feed wrapper for Backtrader.
    Provides real-time data fetching and validation functionality.
    """
    
    def __init__(self, symbol: str, period: str = "1mo", interval: str = "1h", max_candles: Optional[int] = None):
        """
            symbol: Trading symbol (e.g., 'EURUSD=X' for EUR/USD)
            period: Data period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
            interval: Data interval ('1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo')
            max_candles: Maximum number of candlesticks to keep (None for no limit)
        """
        self.symbol = symbol
        self.period = period
        self.interval = interval
        self.max_candles = max_candles
        logger.info(f"Fetching Yahoo Finance data for {symbol} - Period: {period}, Interval: {interval}")
        
        # Fetch data from Yahoo Finance
        try:
            self.ticker = yf.Ticker(symbol)
            self.df = self.ticker.history(period=period, interval=interval)
            
            if self.df.empty:
                raise ValueError(f"No data returned for symbol {symbol}")
            
            logger.info(f"Loaded {len(self.df)} rows from Yahoo Finance")
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
            self.df = self.df.fillna(method='ffill').fillna(method='bfill')
            
            # Limit the number of candlesticks if specified
            if self.max_candles is not None and len(self.df) > self.max_candles:
                logger.info(f"Limiting data to last {self.max_candles} candlesticks (from {len(self.df)} total)")
                self.df = self.df.tail(self.max_candles)
            
        except Exception as e:
            logger.error(f"Error fetching Yahoo Finance data: {e}")
            raise
    
    def get_backtrader_feed(self):
        """
        Get a Backtrader data feed configured for Yahoo Finance data.
        
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
            'period': self.period,
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
