from .yahoo_data_feed import YahooDataFeed
import sys


# only windows can use mt5_data_feed
if sys.platform == 'win32':
    from .mt5_data_feed import MT5DataFeed
    __all__ = ['YahooDataFeed', 'MT5DataFeed']
else:
    from .csv_data_feed import CSVDataFeed
    __all__ = ['CSVDataFeed']
