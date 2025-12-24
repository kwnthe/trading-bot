# Parameter Tuning System Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Quick Start](#quick-start)
5. [Usage Guide](#usage-guide)
6. [Parameter Format](#parameter-format)
7. [Search Methods](#search-methods)
8. [Metrics](#metrics)
9. [Extending the System](#extending-the-system)
10. [Examples](#examples)
11. [Troubleshooting](#troubleshooting)
12. [Best Practices](#best-practices)

---

## Overview

The Parameter Tuning System is an extensible framework for optimizing trading strategy parameters across multiple trading pairs. It supports multiple search algorithms (grid search, Bayesian optimization) and optimization metrics (PnL, Sharpe ratio, profit factor, etc.).

### Key Features

- **Multi-Pair Support**: Tune parameters independently for each trading pair
- **Multiple Search Methods**: Grid search (exhaustive) and Bayesian optimization (smart search)
- **Extensible Metrics**: Easy to add new optimization metrics
- **Progress Tracking**: Visual progress bars for long-running searches
- **Results Display**: Formatted tables showing top N parameter combinations
- **Error Handling**: Graceful handling of backtest failures

---

## Architecture

The system is built with extensibility in mind, using abstract base classes for easy extension:

```
tune_parameters.py (CLI)
    │
    ├── ParameterTuner (orchestrates tuning)
    │
    ├── ParameterSpace (manages parameter definitions)
    │
    ├── SearchStrategy (abstract)
    │   ├── GridSearchStrategy
    │   └── BayesianSearchStrategy
    │
    └── MetricCalculator (abstract)
        ├── TotalPnLMetric
        ├── SharpeRatioMetric
        ├── ProfitFactorMetric
        ├── WinRateMetric
        └── CombinedMetric
```

### Component Responsibilities

- **`ParameterTuner`**: Main orchestrator that coordinates parameter tuning across pairs
- **`ParameterSpace`**: Handles parameter space definition and combination generation
- **`SearchStrategy`**: Abstract interface for search algorithms (grid search, Bayesian, etc.)
- **`MetricCalculator`**: Abstract interface for optimization metrics (PnL, Sharpe, etc.)

---

## Installation

### Prerequisites

- Python 3.8+
- All dependencies from `requirements.txt`

### Install Dependencies

```bash
pip install -r requirements.txt
```

The tuning system requires:
- `scikit-optimize>=0.9.0` (for Bayesian optimization)
- `tqdm>=4.66.0` (for progress bars, optional but recommended)
- `pandas>=2.2.0` (for results display)

**Note**: `tqdm` is optional - the script will work without it, but progress bars won't be displayed.

---

## Quick Start

### Basic Example

```bash
python tune_parameters.py \
    --symbols XAUUSD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --method grid_search \
    --top-n 10 \
    --params '{"XAUUSD": {"ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 100}}}'
```

### Multi-Pair Example

```bash
python tune_parameters.py \
    --symbols XAUUSD EURUSD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --method grid_search \
    --top-n 5 \
    --params '{
        "XAUUSD": {
            "ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 100}
        },
        "EURUSD": {
            "ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 1500, "step": 100},
            "BREAKOUT_MIN_STRENGTH_MICROPIPS": {"start": 50, "end": 500, "step": 50}
        }
    }'
```

---

## Usage Guide

### Command-Line Arguments

#### Required Arguments

- `--symbols` / `-s`: List of trading pairs to tune (e.g., `XAUUSD EURUSD`)
- `--start-date` / `-st`: Start date for backtesting (format: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`)
- `--end-date` / `-en`: End date for backtesting (format: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`)
- `--params` / `-p`: JSON string with tuning parameters per pair

#### Optional Arguments

- `--timeframe` / `-t`: Timeframe for backtesting (default: `H1`)
  - Options: `M1`, `M5`, `M15`, `M30`, `H1`, `H4`, `D1`
- `--method` / `-m`: Search method (default: `grid_search`)
  - Options: `grid_search`, `bayesian`, `binary_search`
  - **Note**: `binary_search` requires exactly 1 parameter per pair
- `--linear-step`: Step size for grid search (overrides step in params)
- `--top-n`: Number of top results to display (default: `10`)
- `--max-candles`: Maximum candles to use in backtest (default: `None`)
- `--no-progress`: Disable progress bars
- `--show-logs`: Show logs from individual backtest runs (default: logs are hidden)

**Note**: By default, logs from individual backtest runs are hidden to keep output clean. Only progress bars and final results are shown. Use `--show-logs` if you need to see detailed backtest output for debugging.
- `--show-logs`: Show logs from individual backtest runs (default: logs are hidden)

### Parameter Format

The `--params` argument expects a JSON string with the following structure:

```json
{
    "PAIR_NAME": {
        "PARAMETER_NAME": {
            "start": <number>,
            "end": <number>,
            "step": <number>
        },
        ...
    },
    ...
}
```

#### Parameter Definition Fields

- **`start`**: Starting value for the parameter (inclusive)
- **`end`**: Ending value for the parameter (inclusive)
- **`step`**: Step size between values (for grid search)

**Note**: For Bayesian optimization, the `step` field is ignored - it searches continuously within the range.

#### Example Parameter Definitions

```json
{
    "XAUUSD": {
        "ZONE_INVERSION_MARGIN_MICROPIPS": {
            "start": 0,
            "end": 2000,
            "step": 100
        },
        "BREAKOUT_MIN_STRENGTH_MICROPIPS": {
            "start": 50,
            "end": 500,
            "step": 50
        },
        "MIN_RISK_DISTANCE_MICROPIPS": {
            "start": 0,
            "end": 100,
            "step": 10
        }
    }
}
```

### Available Parameters

The following parameters can be tuned (use uppercase with underscores):

- `ZONE_INVERSION_MARGIN_MICROPIPS`
- `BREAKOUT_MIN_STRENGTH_MICROPIPS`
- `MIN_RISK_DISTANCE_MICROPIPS`
- `SL_BUFFER_MICROPIPS`
- `SR_CANCELLATION_THRESHOLD_MICROPIPS`
- `TAKE_PROFIT_PIPS`
- `STOP_LOSS_PIPS`
- `RISK_PER_TRADE`
- `RR` (Risk-Reward ratio)

**Note**: Parameter names must match the environment variable names used in your `.env` file (uppercase with underscores).

---

## Search Methods

### Grid Search

**Method**: `grid_search`

Exhaustively tests all parameter combinations within the defined ranges.

**When to Use**:
- Small parameter spaces (< 10,000 combinations)
- When you want to explore the entire parameter space
- When you need deterministic, reproducible results

**Pros**:
- Guaranteed to find the best combination in the defined space
- Deterministic results
- Simple to understand

**Cons**:
- Can be very slow for large parameter spaces
- Exponential time complexity

**Example**:
```bash
python tune_parameters.py \
    --symbols XAUUSD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --method grid_search \
    --linear-step 100 \
    --top-n 10 \
    --params '{"XAUUSD": {"ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 100}}}'
```

**Warning**: If the number of combinations exceeds 10,000, the script will prompt for confirmation before proceeding.

### Binary Search

**Method**: `binary_search`

Efficiently finds the optimal value for a single parameter using a ternary search algorithm (variant of binary search for optimization).

**When to Use**:
- **Exactly 1 parameter** per trading pair
- When you want fast convergence to optimal value
- When the parameter space is large and you want to avoid exhaustive search

**Pros**:
- Very fast convergence (O(log n) complexity)
- Efficient for single parameter optimization
- Finds optimal value with minimal backtests
- Deterministic results

**Cons**:
- **Only works with exactly 1 parameter** (will raise error if multiple parameters provided)
- Assumes unimodal function (single peak/optimum)
- May not work well if the metric has multiple local optima

**Algorithm**: Uses ternary search (divides range into thirds) to efficiently narrow down to the optimal value.

**Example**:
```bash
python tune_parameters.py \
    --symbols XAUUSD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --method binary_search \
    --top-n 10 \
    --params '{"XAUUSD": {"ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 100}}}'
```

**Note**: The `step` parameter is ignored for binary search - it searches continuously within the range. The search continues until the range is smaller than the tolerance (default: 1.0) or maximum iterations (default: 50) is reached.

**Performance**: For a range of 0-2000, binary search typically requires ~20-30 backtests compared to 21 backtests for grid search with step 100. However, binary search converges to the exact optimal value, while grid search only tests discrete values.

### Bayesian Optimization

**Method**: `bayesian`

Uses Gaussian Process-based Bayesian optimization to intelligently search the parameter space.

**When to Use**:
- Large parameter spaces (> 3 parameters or > 1,000 combinations)
- When you want faster results
- When you're willing to trade exhaustive search for speed

**Pros**:
- Much faster than grid search for large spaces
- Intelligently focuses on promising regions
- Good for high-dimensional parameter spaces

**Cons**:
- May not find the absolute best combination
- Results can vary between runs (use `random_state` for reproducibility)
- Requires `scikit-optimize` package

**Example**:
```bash
python tune_parameters.py \
    --symbols XAUUSD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --method bayesian \
    --top-n 10 \
    --params '{"XAUUSD": {"ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 100}}}'
```

**Note**: Bayesian optimization uses 50 iterations by default. You can modify this in the code if needed.

### Choosing the Right Method

| Method | Parameters | Best For | Complexity |
|--------|-----------|----------|------------|
| **Binary Search** | Exactly 1 | Single parameter optimization | O(log n) |
| **Grid Search** | 1-3 | Small spaces, exhaustive search | O(n^k) |
| **Bayesian** | 2+ | Large spaces, smart search | O(iterations) |

---

## Metrics

### Default Metric: Total PnL

By default, the system optimizes for **Total PnL** (Profit and Loss). This is the sum of all profits and losses from completed trades.

### Available Metrics

The system includes several built-in metrics:

1. **TotalPnLMetric**: Total profit and loss (default)
2. **SharpeRatioMetric**: Risk-adjusted return metric
3. **ProfitFactorMetric**: Ratio of gross profit to gross loss
4. **WinRateMetric**: Percentage of winning trades
5. **CombinedMetric**: Weighted combination of multiple metrics

### Using Different Metrics

To use a different metric, you'll need to modify the `tune_parameters.py` script:

```python
from src.utils.tuning import SharpeRatioMetric

# In ParameterTuner initialization:
tuner = ParameterTuner(
    ...
    metric=SharpeRatioMetric(),  # Use Sharpe ratio instead of PnL
    ...
)
```

### Custom Metrics

See [Extending the System](#extending-the-system) for instructions on creating custom metrics.

---

## Extending the System

### Adding a New Metric

1. Create a new class in `src/utils/tuning/metrics.py`:

```python
class MyCustomMetric(MetricCalculator):
    """Calculate my custom metric."""
    
    def calculate(self, stats: Dict[str, Any]) -> float:
        """Calculate custom metric value."""
        # Your calculation here
        return custom_value
    
    @property
    def name(self) -> str:
        return "My Custom Metric"
```

2. Import and use it in `tune_parameters.py`:

```python
from src.utils.tuning import MyCustomMetric

tuner = ParameterTuner(
    ...
    metric=MyCustomMetric(),
    ...
)
```

### Adding a New Search Method

1. Create a new class in `src/utils/tuning/search_strategies.py`:

```python
class MySearchStrategy(SearchStrategy):
    """My custom search strategy."""
    
    def search(
        self,
        parameter_space: ParameterSpace,
        pair: str,
        metric_calculator: MetricCalculator,
        backtest_fn: Callable[[Dict[str, float]], Dict[str, Any]],
        show_progress: bool = True
    ) -> List[SearchResult]:
        """Implement your search algorithm."""
        results = []
        # Your search logic here
        return results
```

2. Add it to `src/utils/tuning/__init__.py`:

```python
from .search_strategies import MySearchStrategy

__all__ = [
    ...
    'MySearchStrategy',
]
```

3. Add support in `tune_parameters.py`:

```python
elif method == "my_search":
    self.search_strategy = MySearchStrategy()
```

### Available Stats in Backtest Results

When implementing custom metrics, you have access to the following statistics from `backtest_fn`:

- `pnl`: Total profit and loss
- `pnl_percentage`: PnL as percentage of initial capital
- `initial_cash`: Starting capital
- `final_equity`: Ending equity
- `total_trades`: Number of completed trades
- `win_rate`: Percentage of winning trades (0.0 to 1.0)
- `avg_win`: Average profit per winning trade
- `avg_loss`: Average loss per losing trade
- `profit_factor`: Ratio of gross profit to gross loss
- `sharpe_ratio`: Risk-adjusted return metric

---

## Examples

### Example 1: Single Parameter, Single Pair (Binary Search)

Tune `ZONE_INVERSION_MARGIN_MICROPIPS` for XAUUSD using binary search (fastest for single parameter):

```bash
python tune_parameters.py \
    --symbols XAUUSD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --method binary_search \
    --top-n 10 \
    --params '{"XAUUSD": {"ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 100}}}'
```

**Note**: Binary search is ideal for single parameter optimization as it converges quickly to the optimal value.

### Example 1b: Single Parameter with Grid Search

If you prefer exhaustive search over all discrete values:

```bash
python tune_parameters.py \
    --symbols XAUUSD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --method grid_search \
    --top-n 5 \
    --params '{"XAUUSD": {"ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 100}}}'
```

### Example 2: Multiple Parameters, Single Pair

Tune multiple parameters for XAUUSD:

```bash
python tune_parameters.py \
    --symbols XAUUSD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --method grid_search \
    --top-n 10 \
    --params '{
        "XAUUSD": {
            "ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 200},
            "BREAKOUT_MIN_STRENGTH_MICROPIPS": {"start": 50, "end": 500, "step": 50},
            "MIN_RISK_DISTANCE_MICROPIPS": {"start": 0, "end": 100, "step": 20}
        }
    }'
```

**Note**: This will test 11 × 10 × 6 = 660 combinations.

### Example 3: Multiple Pairs with Different Parameters

Tune different parameters for different pairs:

```bash
python tune_parameters.py \
    --symbols XAUUSD EURUSD GBPAUD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --method bayesian \
    --top-n 5 \
    --params '{
        "XAUUSD": {
            "ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 100}
        },
        "EURUSD": {
            "ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 1500, "step": 100},
            "BREAKOUT_MIN_STRENGTH_MICROPIPS": {"start": 50, "end": 500, "step": 50}
        },
        "GBPAUD": {
            "ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 1800, "step": 100}
        }
    }'
```

### Example 4: Using Linear Step Override

Override step size for all parameters:

```bash
python tune_parameters.py \
    --symbols XAUUSD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --method grid_search \
    --linear-step 50 \
    --top-n 10 \
    --params '{"XAUUSD": {"ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 100}}}'
```

**Note**: The `--linear-step 50` will override the `step: 100` in the params, so it will use step 50 instead.

### Example 5: Limited Candles for Quick Testing

Test with limited candles for faster iteration:

```bash
python tune_parameters.py \
    --symbols XAUUSD \
    --timeframe H1 \
    --start-date 2025-01-01 \
    --end-date 2025-12-15 \
    --max-candles 1000 \
    --method grid_search \
    --top-n 5 \
    --params '{"XAUUSD": {"ZONE_INVERSION_MARGIN_MICROPIPS": {"start": 0, "end": 2000, "step": 200}}}'
```

---

## Troubleshooting

### Common Issues

#### 1. Module Import Errors

**Error**: `ModuleNotFoundError: No module named 'tqdm'`

**Solution**: Install missing dependencies:
```bash
pip install -r requirements.txt
```

**Note**: `tqdm` is optional - the script will work without it, but progress bars won't be displayed.

#### 2. Config Module Errors

**Error**: `module src.utils.config not in sys.modules`

**Solution**: This error should no longer occur with the current implementation. If you see it, ensure you're using the latest version of `tune_parameters.py`.

#### 3. Parameter Not Found

**Error**: Parameter doesn't seem to affect backtest results

**Possible Causes**:
- Parameter name doesn't match environment variable name (must be uppercase with underscores)
- Parameter is not being read by the strategy code
- Parameter value range doesn't include effective values

**Solution**: 
- Verify parameter names match your `.env` file
- Check that your strategy code reads the parameter from Config
- Expand the parameter range if needed

#### 4. Too Many Combinations

**Warning**: `⚠️ Warning: 50000 combinations will be tested. This may take a long time.`

**Solution**: 
- Use Bayesian optimization instead of grid search
- Reduce parameter ranges
- Increase step sizes
- Reduce number of parameters being tuned simultaneously

#### 5. Backtest Failures

**Error**: `⚠️ Error testing parameters {...}: ...`

**Possible Causes**:
- Invalid parameter values
- Missing data files
- Strategy errors

**Solution**: 
- Check parameter value ranges are valid
- Verify data files exist for the specified date range
- Check strategy code for errors
- The script will continue with other parameter combinations

#### 6. JSON Parsing Errors

**Error**: `Error parsing --params JSON`

**Solution**: 
- Ensure JSON is properly formatted
- Use single quotes around the JSON string in bash
- Escape special characters if needed
- Use a JSON validator to check syntax

#### 7. No Results Returned

**Possible Causes**:
- All backtests failed
- Parameter space is empty
- No trades were executed

**Solution**:
- Check error messages for failed backtests
- Verify parameter ranges are correct
- Ensure date range has sufficient data
- Check that strategy can execute trades with given parameters

---

## Best Practices

### 1. Start Small

Begin with:
- Single parameter
- Small parameter range
- Limited date range or `--max-candles`
- Grid search for small spaces

This helps verify everything works before scaling up.

### 2. Choose Appropriate Search Method

- **Binary Search**: Use for **exactly 1 parameter** (fastest, O(log n))
- **Grid Search**: Use for 1-3 parameters or < 1,000 combinations (exhaustive)
- **Bayesian Optimization**: Use for > 3 parameters or > 1,000 combinations (smart search)

### 3. Parameter Range Selection

- Start with wide ranges to explore the space
- Narrow down based on initial results
- Consider using multiple tuning passes:
  1. Wide range with large steps (coarse search)
  2. Narrow range around best results with small steps (fine search)

### 4. Date Range Selection

- Use sufficient data for statistical significance
- Consider different market conditions (trending, ranging, volatile)
- Avoid overfitting to specific periods

### 5. Step Size Selection

- Smaller steps = more combinations = longer runtime
- Larger steps = fewer combinations = faster but may miss optimal values
- For grid search: Start with larger steps, refine later
- For Bayesian: Step size is ignored (searches continuously)

### 6. Multiple Pairs

- Tune each pair independently (current implementation)
- Consider pair-specific parameter ranges
- Compare results across pairs to identify patterns

### 7. Results Analysis

- Don't just look at the top result
- Examine top N results for patterns
- Check if top results are clustered (indicates robustness)
- Verify results make sense (not outliers due to few trades)

### 8. Validation

- Use out-of-sample data to validate tuned parameters
- Avoid overfitting to the tuning period
- Consider walk-forward optimization for robustness

### 9. Performance Considerations

- Use `--max-candles` for faster iteration during development
- Use `--no-progress` if running in non-interactive environments
- Consider parallelization for large parameter spaces (future enhancement)

### 10. Documentation

- Document your parameter tuning experiments
- Save parameter combinations and results
- Track which parameters were tuned and why

---

## Advanced Usage

### Programmatic Usage

You can also use the tuning system programmatically:

```python
from datetime import datetime
from src.models.timeframe import Timeframe
from src.utils.tuning import ParameterTuner, TotalPnLMetric

# Define parameters
tuning_parameters = {
    "XAUUSD": {
        "ZONE_INVERSION_MARGIN_MICROPIPS": {
            "start": 0,
            "end": 2000,
            "step": 100
        }
    }
}

# Create tuner
tuner = ParameterTuner(
    symbols=["XAUUSD"],
    timeframe=Timeframe.H1,
    start_date=datetime(2025, 1, 1),
    end_date=datetime(2025, 12, 15),
    tuning_parameters=tuning_parameters,
    method="grid_search",
    metric=TotalPnLMetric(),
    show_progress=True
)

# Run tuning
results = tuner.tune_all()

# Display results
tuner.display_top_results(results, top_n=10)

# Access individual results
for pair, pair_results in results.items():
    best_result = pair_results[0]
    print(f"Best parameters for {pair}: {best_result.parameters}")
    print(f"Best metric value: {best_result.metric_value}")
```

### Custom Metric Example

```python
from src.utils.tuning import MetricCalculator
from typing import Dict, Any

class CustomPnLRatioMetric(MetricCalculator):
    """Optimize for PnL per trade."""
    
    def calculate(self, stats: Dict[str, Any]) -> float:
        pnl = stats.get('pnl', 0.0)
        total_trades = stats.get('total_trades', 0)
        if total_trades == 0:
            return 0.0
        return pnl / total_trades
    
    @property
    def name(self) -> str:
        return "PnL per Trade"

# Use it
tuner = ParameterTuner(
    ...
    metric=CustomPnLRatioMetric(),
    ...
)
```

---

## Performance Considerations

### Grid Search Complexity

For grid search, the number of combinations is:
```
total_combinations = product(len(range) for each parameter)
```

Example:
- Parameter 1: 20 values (0 to 2000, step 100)
- Parameter 2: 10 values (50 to 500, step 50)
- Parameter 3: 5 values (0 to 100, step 20)
- Total: 20 × 10 × 5 = 1,000 combinations

If each backtest takes 10 seconds:
- Total time: 1,000 × 10s = 10,000 seconds ≈ 2.8 hours

### Bayesian Optimization Complexity

Bayesian optimization uses a fixed number of iterations (default: 50):
- Total time: 50 × 10s = 500 seconds ≈ 8.3 minutes

**Recommendation**: Use Bayesian optimization for parameter spaces with > 1,000 combinations.

---

## Future Enhancements

Potential improvements for future versions:

1. **Parallel Processing**: Run multiple backtests simultaneously
2. **Resume Capability**: Save progress and resume interrupted tuning
3. **Result Export**: Export results to CSV/JSON for analysis
4. **Visualization**: Plot parameter space and results
5. **More Search Methods**: Random search, genetic algorithms, etc.
6. **Walk-Forward Optimization**: Time-series cross-validation
7. **Parameter Constraints**: Define relationships between parameters
8. **Early Stopping**: Stop if no improvement after N iterations

---

## Support

For issues, questions, or contributions:

1. Check this documentation first
2. Review the troubleshooting section
3. Check existing issues/PRs
4. Create a new issue with:
   - Error messages
   - Parameter configuration
   - Steps to reproduce

---

## License

Same license as the main trading bot project.

