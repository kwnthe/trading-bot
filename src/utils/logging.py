import sys
import os

def log(self, txt, dt=None):
    dt = dt or self.datas[0].datetime.date(0)
   # print(f'{dt.isoformat()}: {txt}')
    print(f'{txt}')


def format_price(value: float) -> str:
    """Format a price value using the configured price_precision."""
    if value is None:
        return 'N/A'
    from src.utils.config import load_config
    config = load_config()
    price_format = config.get_price_format()
    return f'{value:{price_format}}'

def configure_windows_console_for_utf8():
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)
            os.environ['PYTHONUTF8'] = '1'
        except Exception:
            pass