"""
CSV data feed for Backtrader.
Handles CSV files with OHLC data in various formats.
"""

import backtrader as bt
import pandas as pd
from datetime import datetime
from typing import Optional
from loguru import logger
import os
from pathlib import Path


class CSVDataFeed:
    """
    CSV data feed wrapper for Backtrader.
    Provides CSV file loading and validation functionality.
    """
    
    def __init__(self, csv_file_path: str, max_candles: Optional[int] = None, start_index: Optional[int] = None, count: Optional[int] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
        """
        Initialize CSV data feed.
        
        Args:
            csv_file_path: Path to the CSV file
            max_candles: Maximum number of candlesticks to keep (None for no limit)
            start_index: Starting index for data slicing (0-based)
            count: Number of data points to include from start_index
            start_date: Start date for filtering data (inclusive)
            end_date: End date for filtering data (inclusive)
        """
        self.csv_file_path = csv_file_path
        self.max_candles = max_candles
        self.start_index = start_index
        self.count = count
        self.start_date = start_date
        self.end_date = end_date
        
        # Extract symbol and date info from filename if possible
        filename = os.path.basename(csv_file_path)
        self.symbol = self._extract_symbol_from_filename(filename)
        
        logger.info(f"Loading CSV data from {csv_file_path}")
        
        # Load data from CSV
        try:
            self.df = self._load_csv_data()
            
            if self.df.empty:
                raise ValueError(f"No data found in CSV file {csv_file_path}")
            
            logger.info(f"Loaded {len(self.df)} rows from CSV")
            logger.info(f"Date range: {self.df.index.min()} to {self.df.index.max()}")
            
            # Validate required columns
            required_columns = ['Open', 'High', 'Low', 'Close']
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
            
            # Apply date range filtering if provided
            if self.start_date is not None or self.end_date is not None:
                original_len = len(self.df)
                if self.start_date is not None:
                    self.df = self.df[self.df.index >= self.start_date]
                    logger.info(f"Filtered data: {original_len} -> {len(self.df)} rows (after start_date: {self.start_date})")
                if self.end_date is not None:
                    original_len = len(self.df)
                    self.df = self.df[self.df.index <= self.end_date]
                    logger.info(f"Filtered data: {original_len} -> {len(self.df)} rows (after end_date: {self.end_date})")
                
                if self.df.empty:
                    raise ValueError(f"No data found in CSV file {csv_file_path} after applying date range filter ({self.start_date} to {self.end_date})")
            
            # Apply data slicing based on parameters
            if self.start_index is not None and self.count is not None:
                # Slice data from start_index with count number of points
                end_index = self.start_index + self.count
                if self.start_index >= len(self.df):
                    raise ValueError(f"start_index ({self.start_index}) is beyond available data length ({len(self.df)})")
                if end_index > len(self.df):
                    logger.warning(f"Requested end_index ({end_index}) exceeds data length ({len(self.df)}), using available data")
                    end_index = len(self.df)
                logger.info(f"Slicing data from index {self.start_index} to {end_index-1} ({end_index - self.start_index} points)")
                self.df = self.df.iloc[self.start_index:end_index]
            elif self.max_candles is not None and len(self.df) > self.max_candles:
                # Fallback to max_candles behavior if start_index/count not specified
                logger.info(f"Limiting data to last {self.max_candles} candlesticks (from {len(self.df)} total)")
                self.df = self.df.tail(self.max_candles)
            
        except Exception as e:
            logger.error(f"Error loading CSV data: {e}")
            raise
    
    def _extract_symbol_from_filename(self, filename: str) -> str:
        """Extract symbol from filename like 'AUDCHF._H1_2025-01-01_2025-09-22.csv'."""
        try:
            # Remove .csv extension
            name_without_ext = filename.replace('.csv', '')
            # Split by underscore and take the first part
            symbol = name_without_ext.split('_')[0]
            # Remove any dots from symbol
            symbol = symbol.replace('.', '')
            return symbol
        except:
            return "UNKNOWN"
    
    def _load_csv_data(self) -> pd.DataFrame:
        """Load data from CSV file."""
        # Read the CSV file
        df = pd.read_csv(self.csv_file_path)
        
        # Check if we have the expected columns
        expected_columns = ['time', 'open', 'high', 'low', 'close']
        if not all(col in df.columns for col in expected_columns):
            # Try alternative column names
            column_mapping = {
                'datetime': 'time',
                'timestamp': 'time',
                'date': 'time',
                'Open': 'open',
                'High': 'high', 
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            }
            
            # Rename columns if needed
            df = df.rename(columns=column_mapping)
        
        # Convert time column to datetime
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
        else:
            # Provide helpful error message with actual columns found
            actual_columns = list(df.columns) if not df.empty else "CSV file is empty"
            raise ValueError(
                f"No time/datetime column found in CSV file: {self.csv_file_path}\n"
                f"Expected columns: ['time', 'open', 'high', 'low', 'close']\n"
                f"Actual columns: {actual_columns}\n"
                f"CSV file size: {Path(self.csv_file_path).stat().st_size if Path(self.csv_file_path).exists() else 'file not found'} bytes"
            )
        
        # Rename columns to match Backtrader expectations
        column_mapping = {
            'open': 'Open',
            'high': 'High',
            'low': 'Low', 
            'close': 'Close'
        }
        
        # Add volume column if it exists, otherwise create a dummy one
        if 'volume' in df.columns or 'tick_volume' in df.columns:
            volume_col = 'volume' if 'volume' in df.columns else 'tick_volume'
            column_mapping[volume_col] = 'Volume'
        else:
            # Create dummy volume column
            df['Volume'] = 1000
        
        df.rename(columns=column_mapping, inplace=True)
        
        # Ensure we have the required columns
        required_columns = ['Open', 'High', 'Low', 'Close']
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Required column {col} not found in CSV")
        
        # Add Volume column if it doesn't exist
        if 'Volume' not in df.columns:
            df['Volume'] = 1000
        
        return df
    
    def get_backtrader_feed(self):
        """
        Get a Backtrader data feed configured for CSV data.
        
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
            'csv_file': self.csv_file_path,
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
