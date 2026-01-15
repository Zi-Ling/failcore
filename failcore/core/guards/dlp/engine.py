# failcore/core/guards/dlp/engine.py
"""
DLP Engine

Real and NoOp implementations of DLP scanning engine.
"""

from typing import Any, Optional
from .types import DLPResult, DLPFinding
from failcore.core.rules import RuleRegistry, RuleEngine, RuleCategory, RuleAction


class DlpEngine:
    """
    DLP scanning engine interface
    
    Both RealDlpEngine and NoOpDlpEngine implement this interface.
    """
    
    def scan(self, payload: Any) -> DLPResult:
        """
        Scan payload for sensitive data patterns
        
        Args:
            payload: Payload to scan (str, dict, etc.)
        
        Returns:
            DLPResult with matches and metadata
        """
        raise NotImplementedError


class RealDlpEngine(DlpEngine):
    """
    Real DLP engine implementation
    
    Uses rule registry and engine to scan for sensitive patterns.
    """
    
    def __init__(
        self,
        rule_registry: RuleRegistry,
        rule_engine: RuleEngine,
        mode: str = "warn",
        redact: bool = True,
        max_scan_chars: int = 65536,
    ):
        """
        Initialize real DLP engine
        
        Args:
            rule_registry: Rule registry with DLP rules loaded
            rule_engine: Rule engine for evaluation
            mode: Enforcement mode (block/sanitize/warn)
            redact: Whether to redact matched patterns
            max_scan_chars: Maximum characters to scan
        """
        self.rule_registry = rule_registry
        self.rule_engine = rule_engine
        self.mode = mode
        self.redact = redact
        self.max_scan_chars = max_scan_chars
    
    def scan(self, payload: Any) -> DLPResult:
        """Scan payload using DLP rules"""
        import json
        
        # Convert payload to string
        if isinstance(payload, str):
            payload_str = payload
        elif isinstance(payload, dict):
            try:
                payload_str = json.dumps(payload, ensure_ascii=False)
            except Exception:
                payload_str = str(payload)
        else:
            payload_str = str(payload)
        
        # Apply size limit
        if len(payload_str) > self.max_scan_chars:
            payload_str = payload_str[:self.max_scan_chars]
        
        # Evaluate using rule engine
        result = self.rule_engine.evaluate(
            tool_name="__dlp_scan__",
            params={"content": payload_str},
            categories=[
                RuleCategory.DLP_API_KEY,
                RuleCategory.DLP_SECRET,
                RuleCategory.DLP_PII,
                RuleCategory.DLP_PAYMENT,
            ],
        )
        
        # Convert rule matches to DLP findings
        findings = []
        for match in result.matches:
            # Extract matched text (simplified - real implementation would track positions)
            matched_text = payload_str[:50] if len(payload_str) > 50 else payload_str
            
            # Map severity
            severity_map = {
                "critical": 10,
                "high": 8,
                "medium": 5,
                "low": 2,
            }
            severity = severity_map.get(match.rule.severity.value, 5)
            
            finding = DLPFinding(
                pattern_name=match.rule.name,
                category=match.rule.category.value,
                severity=severity,
                matched_text=matched_text,
            )
            findings.append(finding)
        
        return DLPResult(
            matches=findings,
            match_count=len(findings),
            max_severity=max((f.severity for f in findings), default=0),
            reason="ok",
            evidence={
                "scanner": "dlp",
                "mode": self.mode,
                "patterns_checked": len(self.rule_registry.get_rules_by_category(RuleCategory.DLP_API_KEY)),
            },
        )


class NoOpDlpEngine(DlpEngine):
    """
    NoOp DLP engine when module is disabled
    
    Returns empty result with reason="disabled" for observability.
    """
    
    def scan(self, payload: Any) -> DLPResult:
        """NoOp scan - returns empty result"""
        return DLPResult(
            matches=[],
            match_count=0,
            max_severity=0,
            reason="disabled",
            evidence={
                "scanner": "dlp",
                "status": "disabled",
            },
        )
    
    def __repr__(self) -> str:
        return "NoOpDlpEngine(disabled)"


__all__ = [
    "DlpEngine",
    "RealDlpEngine",
    "NoOpDlpEngine",
]
