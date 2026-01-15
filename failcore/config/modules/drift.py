# failcore/config/modules/drift.py
"""
Drift Module Configuration

Configuration for Parameter Drift Detection module.
"""

from dataclasses import dataclass
from .base import ModuleConfig


@dataclass(frozen=True)
class DriftConfig(ModuleConfig):
    """
    Drift module configuration.
    
    enabled: If True, drift detection is registered at startup
    analysis_only: If True, only analyze (read-only), never block
    magnitude_threshold_medium: Threshold for medium severity (2.0 = 2x change)
    magnitude_threshold_high: Threshold for high severity (5.0 = 5x change)
    ignore_fields: Global fields to ignore in drift detection
    """
    
    enabled: bool = True  # Default ON (analysis only)
    analysis_only: bool = True  # Never block, only analyze
    magnitude_threshold_medium: float = 2.0
    magnitude_threshold_high: float = 5.0
    ignore_fields: list[str] = None
    
    def __post_init__(self):
        """Set default ignore_fields if None"""
        if self.ignore_fields is None:
            # frozen dataclass requires object.__setattr__
            object.__setattr__(self, 'ignore_fields', [
                "timestamp",
                "request_id",
                "trace_id",
                "session_id",
                "run_id",
                "step_id",
                "metadata",
                "_internal",
            ])
    
    @classmethod
    def default(cls) -> "DriftConfig":
        """Default drift configuration"""
        return cls(
            enabled=True,
            analysis_only=True,
            magnitude_threshold_medium=2.0,
            magnitude_threshold_high=5.0,
            ignore_fields=None,  # Will be set in __post_init__
        )
    
    @classmethod
    def strict(cls) -> "DriftConfig":
        """Strict drift configuration"""
        return cls(
            enabled=True,
            analysis_only=False,  # Can block on drift
            magnitude_threshold_medium=1.5,  # Lower threshold
            magnitude_threshold_high=3.0,
            ignore_fields=None,
        )
