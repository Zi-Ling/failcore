# failcore/web/services/anomaly/__init__.py
"""
Anomaly Detection - parameter anomaly highlighting rule engine

Provides lightweight rule engine for detecting anomalies in tool arguments.
Focuses on FailCore's responsibility boundary:
- Path traversal
- Dangerous command flags
- URL private network / SSRF
- Magnitude anomalies
- Overly long strings
"""

from .engine import AnomalyEngine, get_anomaly_engine
from .rules import AnomalyRule, RuleSeverity, RuleRiskType

__all__ = [
    "AnomalyEngine",
    "get_anomaly_engine",
    "AnomalyRule",
    "RuleSeverity",
    "RuleRiskType",
]
