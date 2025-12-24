"""
Parameter space management for tuning.
"""

from typing import Dict, List, Any, Tuple
import itertools
from dataclasses import dataclass


@dataclass
class ParameterRange:
    """Represents a parameter range for tuning."""
    start: float
    end: float
    step: float = 1.0
    
    def generate_values(self) -> List[float]:
        """Generate all values in the range."""
        values = []
        current = self.start
        while current <= self.end:
            values.append(current)
            current += self.step
        return values


class ParameterSpace:
    """Manages parameter space definition and combination generation."""
    
    def __init__(self, tuning_parameters: Dict[str, Dict[str, Dict[str, float]]]):
        """
        Initialize parameter space.
        
        Args:
            tuning_parameters: Dictionary mapping pairs to parameter definitions
                Format: {
                    "PAIR": {
                        "PARAM_NAME": {"start": 0, "end": 100, "step": 10}
                    }
                }
        """
        self.tuning_parameters = tuning_parameters
        self._validate_parameters()
    
    def _validate_parameters(self):
        """Validate parameter definitions."""
        for pair, params in self.tuning_parameters.items():
            for param_name, param_def in params.items():
                if 'start' not in param_def or 'end' not in param_def:
                    raise ValueError(f"Parameter {param_name} for {pair} must have 'start' and 'end'")
                if param_def['start'] > param_def['end']:
                    raise ValueError(f"Parameter {param_name} for {pair}: start > end")
                step = param_def.get('step', 1.0)
                if step <= 0:
                    raise ValueError(f"Parameter {param_name} for {pair}: step must be > 0")
    
    def get_parameter_ranges(self, pair: str) -> Dict[str, ParameterRange]:
        """Get parameter ranges for a specific pair."""
        if pair not in self.tuning_parameters:
            return {}
        
        ranges = {}
        for param_name, param_def in self.tuning_parameters[pair].items():
            ranges[param_name] = ParameterRange(
                start=param_def['start'],
                end=param_def['end'],
                step=param_def.get('step', 1.0)
            )
        return ranges
    
    def generate_combinations(self, pair: str) -> List[Dict[str, float]]:
        """
        Generate all parameter combinations for a pair.
        
        Args:
            pair: Trading pair symbol
            
        Returns:
            List of parameter dictionaries
        """
        ranges = self.get_parameter_ranges(pair)
        if not ranges:
            return [{}]  # No parameters to tune
        
        param_names = list(ranges.keys())
        param_values = [ranges[name].generate_values() for name in param_names]
        
        combinations = []
        for combo in itertools.product(*param_values):
            param_dict = {param_names[i]: combo[i] for i in range(len(param_names))}
            combinations.append(param_dict)
        
        return combinations
    
    def get_total_combinations(self, pair: str) -> int:
        """Get total number of combinations for a pair."""
        ranges = self.get_parameter_ranges(pair)
        if not ranges:
            return 1
        
        total = 1
        for param_range in ranges.values():
            values = param_range.generate_values()
            total *= len(values)
        return total
    
    def get_all_pairs(self) -> List[str]:
        """Get list of all pairs with tuning parameters."""
        return list(self.tuning_parameters.keys())

