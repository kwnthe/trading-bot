"""
Metric calculators for evaluating backtest results.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class MetricCalculator(ABC):
    """Abstract base class for metric calculators."""
    
    @abstractmethod
    def calculate(self, stats: Dict[str, Any]) -> float:
        """
        Calculate the metric value from backtest statistics.
        
        Args:
            stats: Dictionary containing backtest statistics
            
        Returns:
            Metric value (higher is better for maximization)
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the metric."""
        pass


class TotalPnLMetric(MetricCalculator):
    """Calculate total PnL as the optimization metric."""
    
    def calculate(self, stats: Dict[str, Any]) -> float:
        """Calculate total PnL."""
        return stats.get('pnl', 0.0)
    
    @property
    def name(self) -> str:
        return "Total PnL"


class SharpeRatioMetric(MetricCalculator):
    """Calculate Sharpe ratio as the optimization metric."""
    
    def calculate(self, stats: Dict[str, Any]) -> float:
        """Calculate Sharpe ratio from returns."""
        sharpe_ratio = stats.get('sharpe_ratio', 0.0)
        return sharpe_ratio if sharpe_ratio is not None else 0.0
    
    @property
    def name(self) -> str:
        return "Sharpe Ratio"


class ProfitFactorMetric(MetricCalculator):
    """Calculate profit factor as the optimization metric."""
    
    def calculate(self, stats: Dict[str, Any]) -> float:
        """Calculate profit factor."""
        profit_factor = stats.get('profit_factor', 0.0)
        # Handle infinity case
        if profit_factor == float('inf'):
            return 1000.0  # Large finite value
        return profit_factor if profit_factor is not None else 0.0
    
    @property
    def name(self) -> str:
        return "Profit Factor"


class WinRateMetric(MetricCalculator):
    """Calculate win rate as the optimization metric."""
    
    def calculate(self, stats: Dict[str, Any]) -> float:
        """Calculate win rate."""
        win_rate = stats.get('win_rate', 0.0)
        return win_rate if win_rate is not None else 0.0
    
    @property
    def name(self) -> str:
        return "Win Rate"


class CombinedMetric(MetricCalculator):
    """Calculate a weighted combination of multiple metrics."""
    
    def __init__(self, metrics: Dict[MetricCalculator, float]):
        """
        Initialize combined metric calculator.
        
        Args:
            metrics: Dictionary mapping metric calculators to their weights
        """
        self.metrics = metrics
        total_weight = sum(metrics.values())
        if total_weight == 0:
            raise ValueError("Total weight cannot be zero")
        # Normalize weights
        self.normalized_weights = {m: w / total_weight for m, w in metrics.items()}
    
    def calculate(self, stats: Dict[str, Any]) -> float:
        """Calculate weighted combination of metrics."""
        total = 0.0
        for metric, weight in self.normalized_weights.items():
            total += metric.calculate(stats) * weight
        return total
    
    @property
    def name(self) -> str:
        metric_names = [m.name for m in self.normalized_weights.keys()]
        weights = list(self.normalized_weights.values())
        return f"Combined ({', '.join(f'{n}:{w:.2f}' for n, w in zip(metric_names, weights))})"

