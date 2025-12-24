#!/usr/bin/env python3
"""
Parameter tuning script for trading strategy optimization.

This script systematically searches for optimal strategy parameters across
multiple trading pairs using grid search or Bayesian optimization.
"""

import sys
import os
import json
import argparse
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
import pandas as pd

# Load .env file before importing Config
script_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(script_dir, ".env")
if not os.path.exists(dotenv_path):
    dotenv_path = os.path.join(os.path.dirname(script_dir), ".env")
load_dotenv(dotenv_path)

# Add src to path
sys.path.insert(0, os.path.join(script_dir, 'src'))

from src.utils.tuning import (
    ParameterSpace,
    GridSearchStrategy,
    BayesianSearchStrategy,
    BinarySearchStrategy,
    TotalPnLMetric,
    MetricCalculator
)
from src.models.timeframe import Timeframe
from main import backtesting


class ParameterTuner:
    """Main class for parameter tuning."""
    
    def __init__(
        self,
        symbols: List[str],
        timeframe: Timeframe,
        start_date: datetime,
        end_date: datetime,
        tuning_parameters: Dict[str, Dict[str, Dict[str, float]]],
        method: str = "grid_search",
        linear_step: float = None,
        metric: MetricCalculator = None,
        max_candles: int = None,
        show_progress: bool = True,
        show_backtest_logs: bool = False
    ):
        """
        Initialize parameter tuner.
        
        Args:
            symbols: List of trading pairs to tune
            timeframe: Timeframe for backtesting
            start_date: Start date for backtesting
            end_date: End date for backtesting
            tuning_parameters: Parameter space definition per pair
            method: Search method ("grid_search" or "bayesian")
            linear_step: Step size for grid search (overrides step in tuning_parameters)
            metric: Metric calculator (defaults to TotalPnLMetric)
            max_candles: Maximum candles to use in backtest
            show_progress: Whether to show progress bars
            show_backtest_logs: Whether to show logs from individual backtest runs (default: False)
        """
        self.symbols = symbols
        self.timeframe = timeframe
        self.start_date = start_date
        self.end_date = end_date
        self.tuning_parameters = tuning_parameters
        self.method = method
        self.linear_step = linear_step
        self.metric = metric or TotalPnLMetric()
        self.max_candles = max_candles
        self.show_progress = show_progress
        self.show_backtest_logs = show_backtest_logs
        
        # Initialize parameter space
        self.parameter_space = ParameterSpace(tuning_parameters)
        
        # Initialize search strategy
        if method == "grid_search":
            self.search_strategy = GridSearchStrategy()
        elif method == "bayesian":
            self.search_strategy = BayesianSearchStrategy()
        elif method == "binary_search":
            self.search_strategy = BinarySearchStrategy()
        else:
            raise ValueError(f"Unknown search method: {method}. Use 'grid_search', 'bayesian', or 'binary_search'")
    
    def _apply_parameters(self, pair: str, params: Dict[str, float]):
        """
        Apply parameters to environment variables and update Config.
        
        Args:
            pair: Trading pair symbol
            params: Parameter dictionary
        """
        # Set environment variables
        for param_name, value in params.items():
            os.environ[param_name] = str(value)
        
        # Reload Config module to pick up new environment variables
        # This is necessary because Config is loaded at import time and cached
        import importlib
        import src.utils.config as config_module
        
        # Reload config module - this will recreate Config = load_config()
        # which reads from the updated environment variables
        importlib.reload(config_module)
        
        # Also reload environment_variables to get the new Config reference
        import src.utils.environment_variables as env_vars_module
        importlib.reload(env_vars_module)
        
        # Force reload of Config in environment_variables module
        # This ensures EnvironmentVariables.access_config_value() uses the updated Config
        import src.utils.config
        env_vars_module.Config = src.utils.config.Config
        
        # Update the Config reference in this module's namespace
        # This ensures any code in this module uses the updated Config
        from src.utils.config import Config
        globals()['Config'] = Config
    
    def _run_backtest(self, pair: str, params: Dict[str, float]) -> Dict[str, Any]:
        """
        Run backtest with given parameters.
        
        Args:
            pair: Trading pair symbol
            params: Parameter dictionary
            
        Returns:
            Statistics dictionary
        """
        # Suppress output during backtesting (hide logs by default)
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        # Apply parameters to environment and reload Config
        # This is necessary because Config is loaded at import time and cached.
        # The strategy code accesses Config via EnvironmentVariables.access_config_value()
        # which uses the global Config object, so we must reload it to pick up new env vars.
        self._apply_parameters(pair, params)
        
        # Verify parameters were applied (for debugging)
        if self.show_backtest_logs:
            from src.utils.config import Config
            print(f"DEBUG: Applied parameters for {pair}:", file=original_stdout)
            for param_name, value in params.items():
                config_value = getattr(Config, param_name.lower(), None)
                print(f"  {param_name}: env={os.environ.get(param_name)}, config={config_value}", file=original_stdout)
        
        # Suppress loguru logs if needed
        loguru_logger = None
        if not self.show_backtest_logs:
            try:
                from loguru import logger
                # Remove default handler and add a null handler
                logger.remove()
                logger.add(lambda msg: None, level="DEBUG")
            except ImportError:
                pass
            
            # Redirect stdout/stderr to devnull to hide backtest logs
            # Progress bars will still work as they use their own output mechanism
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')
        
        try:
            # Run backtest
            # Note: backtesting() calls load_config() internally, which will read
            # the environment variables we set in _apply_parameters()
            results = backtesting(
                symbols=[pair],
                timeframe=self.timeframe,
                start_date=self.start_date,
                end_date=self.end_date,
                max_candles=self.max_candles,
                print_trades=False
            )
            
            stats = results['stats']
            
            # Calculate additional metrics if needed
            if 'sharpe_ratio' not in stats:
                # Calculate Sharpe ratio if we have trade data
                completed_trades = results.get('cerebro', {}).strategy.completed_trades if hasattr(results.get('cerebro', {}), 'strategy') else []
                if completed_trades and len(completed_trades) > 0:
                    import pandas as pd
                    initial_cash = stats.get('initial_cash', 10000)
                    returns = pd.Series([t['pnl'] / initial_cash for t in completed_trades])
                    if len(returns) > 0 and returns.std() > 0:
                        sharpe_ratio = (returns.mean() / returns.std()) * (252 ** 0.5)
                        stats['sharpe_ratio'] = sharpe_ratio
                    else:
                        stats['sharpe_ratio'] = 0.0
                else:
                    stats['sharpe_ratio'] = 0.0
            
            return stats
            
        except Exception as e:
            # Log error to original stderr so it's visible even when logs are suppressed
            import traceback
            error_msg = f"Error testing parameters {params} for {pair}: {str(e)}\n"
            error_msg += traceback.format_exc()
            print(error_msg, file=sys.__stderr__ if hasattr(sys, '__stderr__') else original_stderr, flush=True)
            
            # Return minimal stats on error
            return {
                'pnl': float('-inf'),
                'pnl_percentage': 0.0,
                'total_trades': 0,
                'win_rate': 0.0,
                'profit_factor': 0.0,
                'sharpe_ratio': 0.0,
                'error': str(e)
            }
        finally:
            # Close devnull file if we opened it
            if not self.show_backtest_logs and hasattr(sys.stdout, 'close'):
                try:
                    sys.stdout.close()
                except:
                    pass
            
            # Restore output
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            
            # Restore loguru logger if we suppressed it
            if not self.show_backtest_logs:
                try:
                    from loguru import logger
                    # Re-add default handler
                    logger.remove()
                    logger.add(sys.stderr, level="INFO")
                except ImportError:
                    pass
    
    def tune_pair(self, pair: str) -> List[Any]:
        """
        Tune parameters for a single pair.
        
        Args:
            pair: Trading pair symbol
            
        Returns:
            List of search results
        """
        if pair not in self.parameter_space.get_all_pairs():
            print(f"⚠️  No tuning parameters defined for {pair}, skipping...")
            return []
        
        # Override step size if linear_step is provided
        if self.linear_step is not None and self.method == "grid_search":
            # Modify parameter space to use linear_step
            modified_params = {}
            for p_pair, p_params in self.tuning_parameters.items():
                if p_pair == pair:
                    modified_params[p_pair] = {}
                    for param_name, param_def in p_params.items():
                        modified_params[p_pair][param_name] = {
                            'start': param_def['start'],
                            'end': param_def['end'],
                            'step': self.linear_step
                        }
                else:
                    modified_params[p_pair] = p_params
            parameter_space = ParameterSpace(modified_params)
        else:
            parameter_space = self.parameter_space
        
        # Create backtest function with pair bound
        def backtest_fn(params: Dict[str, float]) -> Dict[str, Any]:
            return self._run_backtest(pair, params)
        
        # Run search
        results = self.search_strategy.search(
            parameter_space=parameter_space,
            pair=pair,
            metric_calculator=self.metric,
            backtest_fn=backtest_fn,
            show_progress=self.show_progress
        )
        
        return results
    
    def tune_all(self) -> Dict[str, List[Any]]:
        """
        Tune parameters for all pairs.
        
        Returns:
            Dictionary mapping pairs to their search results
        """
        all_results = {}
        
        for pair in self.symbols:
            print(f"\n{'='*80}")
            print(f"Tuning parameters for {pair}")
            print(f"{'='*80}")
            
            results = self.tune_pair(pair)
            all_results[pair] = results
            
            if results:
                best = results[0]
                print(f"\n✓ Best result for {pair}:")
                print(f"  Metric ({self.metric.name}): {best.metric_value:.2f}")
                print(f"  Parameters: {best.parameters}")
                print(f"  PnL: ${best.stats.get('pnl', 0):.2f}")
                print(f"  Total Trades: {best.stats.get('total_trades', 0)}")
        
        return all_results
    
    def display_top_results(self, results: Dict[str, List[Any]], top_n: int = 10,
                           show_worst: bool = True, worst_n: int = None):
        """
        Display top N results for each pair, and optionally worst N results.
        
        Args:
            results: Dictionary mapping pairs to search results
            top_n: Number of top results to display
            show_worst: Whether to show worst results (default: True)
            worst_n: Number of worst results to display (defaults to top_n)
        """
        if worst_n is None:
            worst_n = top_n
        
        print(f"\n{'='*80}")
        print(f"TOP {top_n} RESULTS PER PAIR")
        print(f"{'='*80}\n")
        
        for pair, pair_results in results.items():
            if not pair_results:
                continue
            
            print(f"\n{pair}:")
            print("-" * 80)
            
            # Create DataFrame for nice formatting
            data = []
            for i, result in enumerate(pair_results[:top_n], 1):
                row = {
                    'Rank': i,
                    f'{self.metric.name}': f"{result.metric_value:.2f}",
                    **{k: f"{v:.2f}" if isinstance(v, (int, float)) else str(v) 
                       for k, v in result.parameters.items()},
                    'PnL': f"${result.stats.get('pnl', 0):.2f}",
                    'PnL%': f"{result.stats.get('pnl_percentage', 0):.2f}%",
                    'Trades': result.stats.get('total_trades', 0),
                    'Win Rate': f"{result.stats.get('win_rate', 0)*100:.1f}%",
                }
                data.append(row)
            
            df = pd.DataFrame(data)
            print(df.to_string(index=False))
            print()
            
            # Display worst results if enabled
            if show_worst and len(pair_results) > worst_n:
                # Results are sorted descending (best first), so worst are at the end
                # Filter out -inf values
                valid_results = [r for r in pair_results if r.metric_value != float('-inf')]
                
                if len(valid_results) > worst_n:
                    # Get the worst N results (lowest metric values from the end of the list)
                    # Only include results that are actually worse than the top results
                    worst_results = valid_results[-worst_n:]
                    
                    # Filter out results with 0 trades and 0 PnL if they're already in top results
                    # This avoids showing duplicate 0.00 results in both top and worst
                    top_metric_values = {r.metric_value for r in pair_results[:top_n]}
                    worst_results = [
                        r for r in worst_results 
                        if not (r.metric_value == 0.0 and r.stats.get('total_trades', 0) == 0 and 0.0 in top_metric_values)
                    ]
                    
                    # If we filtered some out, take more from the end to fill worst_n
                    if len(worst_results) < worst_n:
                        additional_needed = worst_n - len(worst_results)
                        additional = [
                            r for r in valid_results[-(worst_n + additional_needed):-worst_n]
                            if r not in worst_results and r.metric_value != float('-inf')
                            and not (r.metric_value == 0.0 and r.stats.get('total_trades', 0) == 0 and 0.0 in top_metric_values)
                        ][:additional_needed]
                        worst_results.extend(additional)
                    
                    # Reverse so worst is shown first
                    worst_results.reverse()
                    
                    if worst_results:
                        print(f"\nWORST {len(worst_results)} RESULTS FOR {pair}:")
                        print("-" * 80)
                        
                        worst_data = []
                        for i, result in enumerate(worst_results, 1):
                            row = {
                                'Rank': f"Worst {i}",
                                f'{self.metric.name}': f"{result.metric_value:.2f}",
                                **{k: f"{v:.2f}" if isinstance(v, (int, float)) else str(v) 
                                   for k, v in result.parameters.items()},
                                'PnL': f"${result.stats.get('pnl', 0):.2f}",
                                'PnL%': f"{result.stats.get('pnl_percentage', 0):.2f}%",
                                'Trades': result.stats.get('total_trades', 0),
                                'Win Rate': f"{result.stats.get('win_rate', 0)*100:.1f}%",
                            }
                            worst_data.append(row)
                        
                        worst_df = pd.DataFrame(worst_data)
                        print(worst_df.to_string(index=False))
                        print()


def parse_date(s: str) -> datetime:
    """Parse date string."""
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(
        'Date must be YYYY-MM-DD or YYYY-MM-DD HH:MM:SS'
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Tune trading strategy parameters',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python tune_parameters.py \\
    --symbols XAUUSD EURUSD \\
    --timeframe H1 \\
    --start-date 2025-01-01 \\
    --end-date 2025-12-15 \\
    --method grid_search \\
    --linear-step 100 \\
    --top-n 10 \\
    --params '{"XAUUSD": {"ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 100}}}'
        """
    )
    
    parser.add_argument(
        '--symbols', '-s',
        nargs='+',
        required=True,
        help='Trading pairs to tune (e.g., XAUUSD EURUSD)'
    )
    parser.add_argument(
        '--timeframe', '-t',
        type=Timeframe.from_value,
        default=Timeframe.H1,
        help='Timeframe (M1, M5, M15, M30, H1, H4, D1)'
    )
    parser.add_argument(
        '--start-date', '-st',
        type=parse_date,
        required=True,
        help='Start date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)'
    )
    parser.add_argument(
        '--end-date', '-en',
        type=parse_date,
        required=True,
        help='End date (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)'
    )
    parser.add_argument(
        '--params', '-p',
        type=str,
        required=True,
        help='JSON string with tuning parameters per pair'
    )
    parser.add_argument(
        '--method', '-m',
        choices=['grid_search', 'bayesian', 'binary_search'],
        default='grid_search',
        help='Search method (binary_search requires exactly 1 parameter)'
    )
    parser.add_argument(
        '--linear-step',
        type=float,
        default=None,
        help='Step size for grid search (overrides step in params)'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=10,
        help='Number of top results to display'
    )
    parser.add_argument(
        '--max-candles',
        type=int,
        default=None,
        help='Maximum candles to use in backtest'
    )
    parser.add_argument(
        '--no-progress',
        action='store_true',
        help='Disable progress bars'
    )
    parser.add_argument(
        '--show-logs',
        action='store_true',
        help='Show logs from individual backtest runs (default: logs are hidden)'
    )
    parser.add_argument(
        '--no-worst',
        action='store_true',
        help='Disable display of worst results (default: worst results are shown)'
    )
    parser.add_argument(
        '--worst-n',
        type=int,
        default=None,
        help='Number of worst results to display (defaults to --top-n value)'
    )
    
    args = parser.parse_args()
    
    # Parse tuning parameters
    try:
        tuning_parameters = json.loads(args.params)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing --params JSON: {e}")
        sys.exit(1)
    
    # Create tuner
    tuner = ParameterTuner(
        symbols=args.symbols,
        timeframe=args.timeframe,
        start_date=args.start_date,
        end_date=args.end_date,
        tuning_parameters=tuning_parameters,
        method=args.method,
        linear_step=args.linear_step,
        max_candles=args.max_candles,
        show_progress=not args.no_progress,
        show_backtest_logs=args.show_logs
    )
    
    # Run tuning
    results = tuner.tune_all()
    
    # Display results
    tuner.display_top_results(
        results, 
        top_n=args.top_n,
        show_worst=not args.no_worst,
        worst_n=args.worst_n
    )
    
    print("\n✓ Parameter tuning complete!")


if __name__ == '__main__':
    main()

