"""
Semantic Guard - Verdict

Verdict model for semantic checks
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from enum import Enum
from datetime import datetime, timezone


class VerdictAction(str, Enum):
    """Verdict actions"""
    ALLOW = "allow"      # Pass through
    WARN = "warn"        # Allow but warn
    LOG = "log"          # Allow but log
    BLOCK = "block"      # Block execution
    SANITIZE = "sanitize"  # Sanitize parameters
    WARN_APPROVAL_NEEDED = "warn_approval_needed"  # Warn that approval is needed


@dataclass
class SemanticVerdict:
    """
    Semantic check verdict
    
    Contains:
    - Action (allow/warn/block)
    - Violated rules
    - Explanation
    - Evidence
    """
    action: VerdictAction
    violations: List[Any]  # List of Rule from failcore.core.rules
    tool_name: str
    params: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    @property
    def is_blocked(self) -> bool:
        """Check if blocked"""
        return self.action == VerdictAction.BLOCK
    
    @property
    def has_violations(self) -> bool:
        """Check if has violations"""
        return len(self.violations) > 0
    
    def get_explanation(self) -> str:
        """Get human-readable explanation"""
        if not self.has_violations:
            return f"✓ No violations detected for {self.tool_name}"
        
        lines = [f"✗ Semantic violations detected for {self.tool_name}:"]
        for rule in self.violations:
            lines.append(f"  - [{rule.severity.value.upper()}] {rule.name}")
            lines.append(f"    {rule.description}")
        
        return "\n".join(lines)
    
    def get_evidence(self) -> Dict[str, Any]:
        """Get evidence for audit"""
        return {
            "tool_name": self.tool_name,
            "params": self._sanitize_params(self.params),
            "violations": [
                {
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "category": rule.category.value,
                    "severity": rule.severity.value,
                    "description": rule.description,
                }
                for rule in self.violations
            ],
            "action": self.action.value,
            "timestamp": self.timestamp,
        }
    
    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize params for logging (mask secrets)"""
        # Simple sanitization - mask values that look like secrets
        import re
        
        sanitized = {}
        secret_pattern = re.compile(r'(?i)(key|token|password|secret)')
        
        for key, value in params.items():
            if isinstance(value, str):
                if secret_pattern.search(key):
                    sanitized[key] = "***REDACTED***"
                elif len(value) > 100:
                    sanitized[key] = value[:100] + "...(truncated)"
                else:
                    sanitized[key] = value
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_params(value)
            else:
                sanitized[key] = value
        
        return sanitized
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict"""
        return {
            "action": self.action.value,
            "has_violations": self.has_violations,
            "violation_count": len(self.violations),
            "explanation": self.get_explanation(),
            "evidence": self.get_evidence(),
        }


__all__ = ["VerdictAction", "SemanticVerdict"]
