"""
Semantic Enricher - Semantic pattern annotation

Scans egress events for semantic anomalies and malicious patterns.
Adds semantic analysis results to evidence for audit trail.

Outputs:
- event.evidence["semantic_verdict"]: "clean" | "suspicious" | "malicious"
- event.evidence["semantic_matches"]: list of matched rule names
- event.evidence["semantic_confidence"]: confidence score (0-1)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from ..types import EgressEvent
from failcore.core.rules import RuleRegistry, RuleSeverity
try:
    from failcore.core.guards.semantic.detectors import SemanticDetector
    from failcore.core.guards.semantic.verdict import VerdictAction
except ImportError:
    SemanticDetector = None
    VerdictAction = None


class SemanticEnricher:
    """
    Semantic enricher for egress events
    
    Responsibilities:
    - Scan events for semantic anomaly patterns
    - Add semantic analysis results to evidence
    - Tag suspicious/malicious patterns for audit
    - Never block traffic (post-execution analysis)
    
    Design:
    - Uses guards/semantic detection logic
    - Lightweight best-effort analysis
    - JSON-serializable output
    """
    
    def __init__(
        self,
        detector: Optional[SemanticDetector] = None,
        registry: Optional[RuleRegistry] = None,
        min_severity: RuleSeverity = RuleSeverity.MEDIUM,
    ):
        """
        Initialize semantic enricher
        
        Args:
            detector: Semantic detector (uses default if None)
            registry: Rule registry (uses default if None)
            min_severity: Minimum severity to report
        """
        self.registry = registry or RuleRegistry()
        self.detector = detector or SemanticDetector(
            registry=self.registry,
            min_severity=min_severity,
        )
        self.min_severity = min_severity
    
    def enrich(self, event: EgressEvent) -> None:
        """
        Enrich event with semantic analysis
        
        Args:
            event: Egress event to enrich
        """
        evidence = getattr(event, "evidence", None)
        if evidence is None:
            evidence = {}
            event.evidence = evidence  # type: ignore[assignment]
        if not isinstance(evidence, dict):
            return
        
        # Extract tool and params from evidence
        tool_name = evidence.get("tool", "")
        params = evidence.get("params", {})
        
        if not tool_name:
            # No tool info, skip semantic analysis
            evidence["semantic_verdict"] = "unknown"
            return
        
        # Run semantic detection
        try:
            verdict = self.detector.check_tool_call(tool_name, params)
            
            if verdict:
                # Semantic issue detected
                evidence["semantic_verdict"] = self._verdict_to_label(verdict.action)
                evidence["semantic_matches"] = [verdict.rule.name]
                evidence["semantic_confidence"] = verdict.confidence
                evidence["semantic_severity"] = verdict.rule.severity.value
                evidence["semantic_reason"] = verdict.reason
                
                # Add rule details
                evidence["semantic_rule_category"] = verdict.rule.category.value
            else:
                # Clean
                evidence["semantic_verdict"] = "clean"
                evidence["semantic_matches"] = []
                evidence["semantic_confidence"] = 1.0
        
        except Exception as e:
            # Defensive: never crash pipeline
            evidence["semantic_verdict"] = "error"
            evidence["semantic_error"] = str(e)
    
    def _verdict_to_label(self, action: VerdictAction) -> str:
        """
        Convert verdict action to label
        
        Args:
            action: Verdict action
        
        Returns:
            Label string
        """
        if action == VerdictAction.BLOCK:
            return "malicious"
        elif action == VerdictAction.WARN:
            return "suspicious"
        elif action == VerdictAction.ALLOW:
            return "clean"
        else:
            return "unknown"


__all__ = ["SemanticEnricher"]
