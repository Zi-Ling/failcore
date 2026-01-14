# failcore/core/replay/drift/proxy.py
"""
Drift Engine Configuration - field ignore rules and normalization settings

Provides default configuration for parameter normalization and drift detection.
Fields in the ignore list are excluded from drift comparison.
"""

from typing import List, Set, Dict, Any, Optional
from enum import Enum


# Default fields to ignore during normalization (dynamic fields that change every call)
DEFAULT_IGNORE_FIELDS: Set[str] = {
    "request_id",
    "timestamp",
    "ts",
    "id",
    "uuid",
    "trace_id",
    "span_id",
    "correlation_id",
    "session_id",
    "transaction_id",
    "call_id",
    "invocation_id",
    "execution_id",
    "run_id",
    "task_id",
    "job_id",
}

# Tool-specific ignore fields (can be extended)
TOOL_IGNORE_FIELDS: Dict[str, Set[str]] = {
    # Example: "http_request": {"request_id", "timestamp"},
    # Add tool-specific ignore fields here
}

# Fields that should be treated as unordered sets (lists that should be sorted)
UNORDERED_SET_FIELDS: Set[str] = {
    "tags",
    "keywords",
    "categories",
    "labels",
    "features",
    "attributes",
    "metadata",
    "properties",
    "fields",
    "columns",
    "indexes",
    "ids",  # List of IDs where order doesn't matter
    "dependencies",
    "depends_on",
}

# Drift detection thresholds
MAGNITUDE_THRESHOLD_MEDIUM: float = 3.0  # 3x change = medium severity
MAGNITUDE_THRESHOLD_HIGH: float = 10.0  # 10x change = high severity

# Drift score weights (per change type)
DRIFT_WEIGHT_VALUE_CHANGED: float = 1.0  # Low weight
DRIFT_WEIGHT_MAGNITUDE_CHANGED: float = 2.0  # Medium weight
DRIFT_WEIGHT_DOMAIN_CHANGED: float = 5.0  # High weight

# Inflection point detection thresholds
INFLECTION_THRESHOLD_HIGH: float = 10.0  # Absolute threshold for high drift
INFLECTION_CHANGE_RATE: float = 2.0  # 2x previous drift = inflection point

# Baseline strategy options
class BaselineStrategy(str, Enum):
    """Baseline generation strategy"""
    FIRST_OCCURRENCE = "first_occurrence"  # Use first occurrence (default, simple)
    MEDIAN = "median"  # Use median value (robust to outliers)
    PERCENTILE = "percentile"  # Use percentile value (configurable)
    SEGMENTED = "segmented"  # Build baselines per segment


class DriftConfig:
    """
    Configuration for drift detection
    
    Encapsulates normalization and comparison settings.
    """
    
    def __init__(
        self,
        ignore_fields: Optional[Set[str]] = None,
        tool_ignore_fields: Optional[Dict[str, Set[str]]] = None,
        unordered_set_fields: Optional[Set[str]] = None,
        normalize_paths: bool = True,
        path_separator: str = "/",
        normalize_whitespace: bool = True,
        magnitude_threshold_medium: float = MAGNITUDE_THRESHOLD_MEDIUM,
        magnitude_threshold_high: float = MAGNITUDE_THRESHOLD_HIGH,
        drift_weight_value_changed: float = DRIFT_WEIGHT_VALUE_CHANGED,
        drift_weight_magnitude_changed: float = DRIFT_WEIGHT_MAGNITUDE_CHANGED,
        drift_weight_domain_changed: float = DRIFT_WEIGHT_DOMAIN_CHANGED,
        inflection_threshold_high: float = INFLECTION_THRESHOLD_HIGH,
        inflection_change_rate: float = INFLECTION_CHANGE_RATE,
        baseline_strategy: BaselineStrategy = BaselineStrategy.FIRST_OCCURRENCE,
        baseline_percentile: float = 50.0,
        baseline_segment_window: Optional[int] = None,
    ):
        """
        Initialize drift configuration
        
        Args:
            ignore_fields: Fields to ignore during normalization
            tool_ignore_fields: Tool-specific ignore fields
            unordered_set_fields: Fields that should be treated as unordered sets
            normalize_paths: Whether to normalize path separators
            path_separator: Path separator to use (default: "/")
            normalize_whitespace: Whether to trim whitespace from strings
            magnitude_threshold_medium: Medium severity threshold for magnitude changes (default: 3.0)
            magnitude_threshold_high: High severity threshold for magnitude changes (default: 10.0)
            drift_weight_value_changed: Weight for value_changed drift (default: 1.0)
            drift_weight_magnitude_changed: Weight for magnitude_changed drift (default: 2.0)
            drift_weight_domain_changed: Weight for domain_changed drift (default: 5.0)
            inflection_threshold_high: High threshold for inflection point detection (default: 10.0)
            inflection_change_rate: Change rate multiplier for inflection point detection (default: 2.0)
            baseline_strategy: Baseline generation strategy (default: FIRST_OCCURRENCE)
            baseline_percentile: Percentile for percentile baseline (default: 50.0)
            baseline_segment_window: Window size for segmented baseline (default: None)
        """
        self.ignore_fields = ignore_fields or DEFAULT_IGNORE_FIELDS.copy()
        self.tool_ignore_fields = tool_ignore_fields or TOOL_IGNORE_FIELDS.copy()
        self.unordered_set_fields = unordered_set_fields or UNORDERED_SET_FIELDS.copy()
        self.normalize_paths = normalize_paths
        self.path_separator = path_separator
        self.normalize_whitespace = normalize_whitespace
        
        # Drift detection thresholds
        self.magnitude_threshold_medium = magnitude_threshold_medium
        self.magnitude_threshold_high = magnitude_threshold_high
        
        # Drift score weights
        self.drift_weight_value_changed = drift_weight_value_changed
        self.drift_weight_magnitude_changed = drift_weight_magnitude_changed
        self.drift_weight_domain_changed = drift_weight_domain_changed
        
        # Inflection point detection
        self.inflection_threshold_high = inflection_threshold_high
        self.inflection_change_rate = inflection_change_rate
        
        # Baseline strategy
        self.baseline_strategy = baseline_strategy
        self.baseline_percentile = baseline_percentile
        self.baseline_segment_window = baseline_segment_window
    
    def get_ignore_fields(self, tool_name: str) -> Set[str]:
        """
        Get ignore fields for a specific tool
        
        Args:
            tool_name: Tool name
        
        Returns:
            Set of field names to ignore
        """
        ignore = self.ignore_fields.copy()
        if tool_name in self.tool_ignore_fields:
            ignore.update(self.tool_ignore_fields[tool_name])
        return ignore
    
    def should_ignore_field(self, tool_name: str, field_name: str) -> bool:
        """
        Check if a field should be ignored
        
        Args:
            tool_name: Tool name
            field_name: Field name
        
        Returns:
            True if field should be ignored
        """
        return field_name in self.get_ignore_fields(tool_name)
    
    def is_unordered_set_field(self, field_name: str) -> bool:
        """
        Check if a field should be treated as an unordered set
        
        Args:
            field_name: Field name
        
        Returns:
            True if field should be sorted as a set
        """
        return field_name in self.unordered_set_fields


# Global default configuration
_default_config: Optional[DriftConfig] = None


def get_default_config() -> DriftConfig:
    """Get default drift configuration"""
    global _default_config
    if _default_config is None:
        _default_config = DriftConfig()
    return _default_config


def set_default_config(config: DriftConfig) -> None:
    """Set default drift configuration"""
    global _default_config
    _default_config = config


__all__ = [
    "DriftConfig",
    "BaselineStrategy",
    "get_default_config",
    "set_default_config",
    "DEFAULT_IGNORE_FIELDS",
    "TOOL_IGNORE_FIELDS",
    "UNORDERED_SET_FIELDS",
    "MAGNITUDE_THRESHOLD_MEDIUM",
    "MAGNITUDE_THRESHOLD_HIGH",
    "DRIFT_WEIGHT_VALUE_CHANGED",
    "DRIFT_WEIGHT_MAGNITUDE_CHANGED",
    "DRIFT_WEIGHT_DOMAIN_CHANGED",
    "INFLECTION_THRESHOLD_HIGH",
    "INFLECTION_CHANGE_RATE",
]
