# failcore/web/services/anomaly/engine.py
"""
Anomaly Engine - rule engine for parameter anomaly detection

Applies rules to tool arguments and returns anomalies.
"""

from typing import Dict, Any, List, Optional

from .rules import AnomalyRule, RuleSeverity, RuleRiskType, DEFAULT_RULES


class AnomalyEngine:
    """
    Anomaly detection engine
    
    Applies rules to tool arguments and returns structured anomalies.
    """
    
    def __init__(self, rules: Optional[List[AnomalyRule]] = None):
        """
        Initialize anomaly engine
        
        Args:
            rules: Optional list of rules (uses DEFAULT_RULES if None)
        """
        self.rules = rules or DEFAULT_RULES
    
    def analyze(
        self,
        tool: str,
        args: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze tool arguments for anomalies
        
        Args:
            tool: Tool name
            args: Tool arguments
            metadata: Optional tool metadata
        
        Returns:
            List of anomaly dicts:
            {
                "field_path": str,
                "severity": "low" | "medium" | "high" | "critical",
                "risk_type": str,
                "reason": str,
                "explanation": str,
            }
        """
        anomalies = []
        
        for rule in self.rules:
            if rule.check(tool, args, metadata):
                anomaly = {
                    "field_path": rule.field_path,
                    "severity": rule.severity.value,
                    "risk_type": rule.risk_type.value,
                    "reason": rule.reason,
                    "explanation": rule.explanation,
                }
                anomalies.append(anomaly)
        
        return anomalies


# Singleton instance
_anomaly_engine: Optional[AnomalyEngine] = None


def get_anomaly_engine() -> AnomalyEngine:
    """Get anomaly engine singleton"""
    global _anomaly_engine
    if _anomaly_engine is None:
        _anomaly_engine = AnomalyEngine()
    return _anomaly_engine


__all__ = ["AnomalyEngine", "get_anomaly_engine"]
