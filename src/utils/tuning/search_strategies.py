"""
Search strategies for parameter optimization.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass
from .metrics import MetricCalculator
from .parameter_space import ParameterSpace
import numpy as np

# Make tqdm optional
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    # Create a no-op tqdm replacement
    def tqdm(iterable, desc=None, **kwargs):
        return iterable


@dataclass
class SearchResult:
    """Result from a parameter search."""
    parameters: Dict[str, float]
    metric_value: float
    stats: Dict[str, Any]
    pair: str


class SearchStrategy(ABC):
    """Abstract base class for search strategies."""
    
    @abstractmethod
    def search(
        self,
        parameter_space: ParameterSpace,
        pair: str,
        metric_calculator: MetricCalculator,
        backtest_fn: Callable[[Dict[str, float]], Dict[str, Any]],
        show_progress: bool = True
    ) -> List[SearchResult]:
        """
        Search for optimal parameters.
        
        Args:
            parameter_space: Parameter space definition
            pair: Trading pair symbol
            metric_calculator: Metric calculator to evaluate results
            backtest_fn: Function that runs backtest with given parameters and returns stats
            show_progress: Whether to show progress bar
            
        Returns:
            List of search results sorted by metric value (best first)
        """
        pass


class GridSearchStrategy(SearchStrategy):
    """Exhaustive grid search strategy."""
    
    def search(
        self,
        parameter_space: ParameterSpace,
        pair: str,
        metric_calculator: MetricCalculator,
        backtest_fn: Callable[[Dict[str, float]], Dict[str, Any]],
        show_progress: bool = True
    ) -> List[SearchResult]:
        """Perform grid search over all parameter combinations."""
        combinations = parameter_space.generate_combinations(pair)
        total = len(combinations)
        
        if total > 10000:
            print(f"⚠️  Warning: {total} combinations will be tested. This may take a long time.")
            response = input("Continue? (y/n): ")
            if response.lower() != 'y':
                return []
        
        results = []
        iterator = tqdm(combinations, desc=f"Grid search {pair}") if (show_progress and HAS_TQDM) else combinations
        
        for params in iterator:
            try:
                stats = backtest_fn(params)
                metric_value = metric_calculator.calculate(stats)
                results.append(SearchResult(
                    parameters=params,
                    metric_value=metric_value,
                    stats=stats,
                    pair=pair
                ))
            except Exception as e:
                print(f"⚠️  Error testing parameters {params}: {e}")
                continue
        
        # Sort by metric value (descending - best first)
        results.sort(key=lambda x: x.metric_value, reverse=True)
        return results


class BayesianSearchStrategy(SearchStrategy):
    """Bayesian optimization search strategy using scikit-optimize."""
    
    def __init__(self, n_iterations: int = 50, random_state: Optional[int] = None):
        """
        Initialize Bayesian search strategy.
        
        Args:
            n_iterations: Number of iterations for Bayesian optimization
            random_state: Random seed for reproducibility
        """
        self.n_iterations = n_iterations
        self.random_state = random_state
        
        try:
            from skopt import gp_minimize
            from skopt.space import Real, Integer
            from skopt.utils import use_named_args
            self.gp_minimize = gp_minimize
            self.Real = Real
            self.Integer = Integer
            self.use_named_args = use_named_args
        except ImportError:
            raise ImportError(
                "scikit-optimize is required for Bayesian search. "
                "Install it with: pip install scikit-optimize"
            )
    
    def search(
        self,
        parameter_space: ParameterSpace,
        pair: str,
        metric_calculator: MetricCalculator,
        backtest_fn: Callable[[Dict[str, float]], Dict[str, Any]],
        show_progress: bool = True
    ) -> List[SearchResult]:
        """Perform Bayesian optimization search."""
        ranges = parameter_space.get_parameter_ranges(pair)
        if not ranges:
            # No parameters to tune
            params = {}
            stats = backtest_fn(params)
            metric_value = metric_calculator.calculate(stats)
            return [SearchResult(
                parameters=params,
                metric_value=metric_value,
                stats=stats,
                pair=pair
            )]
        
        # Build search space for skopt
        dimensions = []
        param_names = []
        for param_name, param_range in ranges.items():
            param_names.append(param_name)
            # Use Real for continuous parameters
            dimensions.append(self.Real(
                low=param_range.start,
                high=param_range.end,
                name=param_name
            ))
        
        # Store results during optimization
        all_results = []
        
        @self.use_named_args(dimensions=dimensions)
        def objective(**kwargs):
            """Objective function for optimization (minimize negative metric)."""
            params = kwargs
            try:
                stats = backtest_fn(params)
                metric_value = metric_calculator.calculate(stats)
                # Store result
                all_results.append(SearchResult(
                    parameters=params.copy(),
                    metric_value=metric_value,
                    stats=stats,
                    pair=pair
                ))
                # Return negative because gp_minimize minimizes
                return -metric_value
            except Exception as e:
                print(f"⚠️  Error testing parameters {params}: {e}")
                return 1e10  # Large penalty for failed runs
        
        # Run Bayesian optimization
        if show_progress:
            print(f"Running Bayesian optimization for {pair} ({self.n_iterations} iterations)...")
        
        result = self.gp_minimize(
            func=objective,
            dimensions=dimensions,
            n_calls=self.n_iterations,
            random_state=self.random_state,
            verbose=show_progress
        )
        
        # Sort results by metric value (descending - best first)
        all_results.sort(key=lambda x: x.metric_value, reverse=True)
        return all_results


class BinarySearchStrategy(SearchStrategy):
    """Binary search strategy for single parameter optimization."""
    
    def __init__(self, tolerance: float = 1.0, max_iterations: int = 50):
        """
        Initialize binary search strategy.
        
        Args:
            tolerance: Minimum difference between bounds to continue searching
            max_iterations: Maximum number of iterations to prevent infinite loops
        """
        self.tolerance = tolerance
        self.max_iterations = max_iterations
    
    def search(
        self,
        parameter_space: ParameterSpace,
        pair: str,
        metric_calculator: MetricCalculator,
        backtest_fn: Callable[[Dict[str, float]], Dict[str, Any]],
        show_progress: bool = True
    ) -> List[SearchResult]:
        """Perform binary search optimization for a single parameter."""
        ranges = parameter_space.get_parameter_ranges(pair)
        
        if len(ranges) == 0:
            # No parameters to tune
            params = {}
            stats = backtest_fn(params)
            metric_value = metric_calculator.calculate(stats)
            return [SearchResult(
                parameters=params,
                metric_value=metric_value,
                stats=stats,
                pair=pair
            )]
        
        if len(ranges) > 1:
            raise ValueError(
                f"Binary search requires exactly 1 parameter, but {len(ranges)} parameters were provided. "
                f"Use grid_search or bayesian for multiple parameters."
            )
        
        # Get the single parameter
        param_name = list(ranges.keys())[0]
        param_range = ranges[param_name]
        
        # Get original stdout for progress output
        import sys
        original_stdout = sys.__stdout__ if hasattr(sys, '__stdout__') else sys.stdout
        
        if show_progress:
            print(f"Binary search for {pair} - Parameter: {param_name}", file=original_stdout)
            print(f"  Range: [{param_range.start}, {param_range.end}]", file=original_stdout)
            print(f"  Tolerance: {self.tolerance}", file=original_stdout)
            print(f"  Testing initial endpoints...", file=original_stdout, flush=True)
        
        # Binary search implementation
        left = param_range.start
        right = param_range.end
        results = []
        iteration = 0
        
        # Test initial endpoints
        if show_progress:
            print(f"  Testing left endpoint ({left})...", file=original_stdout, flush=True)
        left_stats = backtest_fn({param_name: left})
        if show_progress:
            print(f"  Testing right endpoint ({right})...", file=original_stdout, flush=True)
        right_stats = backtest_fn({param_name: right})
        left_metric = metric_calculator.calculate(left_stats)
        right_metric = metric_calculator.calculate(right_stats)
        
        results.append(SearchResult(
            parameters={param_name: left},
            metric_value=left_metric,
            stats=left_stats,
            pair=pair
        ))
        results.append(SearchResult(
            parameters={param_name: right},
            metric_value=right_metric,
            stats=right_stats,
            pair=pair
        ))
        
        # Binary search loop
        if show_progress and HAS_TQDM:
            from tqdm import tqdm
            pbar = tqdm(total=self.max_iterations, desc=f"Binary search {pair}", unit="iter", file=original_stdout)
        else:
            pbar = None
        
        try:
            while (right - left) > self.tolerance and iteration < self.max_iterations:
                iteration += 1
                
                # Calculate two midpoints (ternary search approach for optimization)
                mid1 = left + (right - left) / 3
                mid2 = right - (right - left) / 3
                
                # Update progress bar
                if pbar:
                    best_so_far = max(results, key=lambda x: x.metric_value)
                    pbar.set_description(f"Binary search {pair} [Range: {left:.0f}-{right:.0f}, Best: {best_so_far.metric_value:.2f}]")
                    pbar.update(1)
                elif show_progress:
                    best_so_far = max(results, key=lambda x: x.metric_value)
                    print(f"  Iteration {iteration}/{self.max_iterations}: Testing range [{left:.2f}, {right:.2f}], "
                          f"Best so far: {best_so_far.metric_value:.2f}", file=original_stdout, flush=True)
                
                if show_progress and not pbar:
                    print(f"    Testing mid1={mid1:.2f}...", file=original_stdout, flush=True)
                
                # Test midpoints
                mid1_stats = backtest_fn({param_name: mid1})
                if show_progress and not pbar:
                    print(f"    Testing mid2={mid2:.2f}...", file=original_stdout, flush=True)
                mid2_stats = backtest_fn({param_name: mid2})
                mid1_metric = metric_calculator.calculate(mid1_stats)
                mid2_metric = metric_calculator.calculate(mid2_stats)
                
                results.append(SearchResult(
                    parameters={param_name: mid1},
                    metric_value=mid1_metric,
                    stats=mid1_stats,
                    pair=pair
                ))
                results.append(SearchResult(
                    parameters={param_name: mid2},
                    metric_value=mid2_metric,
                    stats=mid2_stats,
                    pair=pair
                ))
                
                # Narrow search space based on which region has better metric
                if mid1_metric > mid2_metric:
                    # Left region is better, discard right region
                    right = mid2
                else:
                    # Right region is better, discard left region
                    left = mid1
        finally:
            if pbar:
                pbar.close()
            elif show_progress:
                print(file=original_stdout)  # New line after progress updates
        
        # Test final midpoint
        final_mid = (left + right) / 2
        if show_progress and not pbar:
            print(f"  Testing final midpoint ({final_mid:.2f})...", file=original_stdout, flush=True)
        final_stats = backtest_fn({param_name: final_mid})
        final_metric = metric_calculator.calculate(final_stats)
        results.append(SearchResult(
            parameters={param_name: final_mid},
            metric_value=final_metric,
            stats=final_stats,
            pair=pair
        ))
        
        # Sort results by metric value (descending - best first)
        results.sort(key=lambda x: x.metric_value, reverse=True)
        
        if show_progress:
            best = results[0]
            print(f"  Completed in {iteration} iterations", file=original_stdout, flush=True)
            print(f"  Best: {best.metric_value:.2f} at {best.parameters}", file=original_stdout, flush=True)
        
        return results

