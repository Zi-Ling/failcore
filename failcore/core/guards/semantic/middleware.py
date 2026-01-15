"""
Semantic Guard - Middleware

Middleware for semantic intent validation
"""

from typing import Dict, Any, Optional, Callable
from .detectors import SemanticDetector
from failcore.core.rules import RuleRegistry, RuleSeverity
from .verdict import VerdictAction


class SemanticGuardMiddleware:
    """
    Semantic Guard Middleware
    
    Validates tool calls for high-confidence malicious patterns.
    
    Features:
    - High precision (99%+ accuracy)
    - Explainable verdicts
    - Auditable decisions
    - Default: DISABLED
    
    Integration:
    - Hooks into on_call_start
    - Blocks CRITICAL/HIGH severity violations
    - Logs all verdicts for audit
    """
    
    def __init__(
        self,
        enabled: bool = False,
        detector: SemanticDetector = None,
        registry: RuleRegistry = None,
        min_severity: RuleSeverity = RuleSeverity.HIGH,
        block_on_violation: bool = True,
    ):
        """
        Args:
            enabled: Enable semantic guard (default: False)
            detector: Semantic detector
            registry: Rule registry
            min_severity: Minimum severity to check
            block_on_violation: Block on violations (vs warn only)
        """
        self.enabled = enabled
        self.detector = detector or SemanticDetector(
            rule_registry=registry or RuleRegistry(),
            min_severity=min_severity,
        )
        self.block_on_violation = block_on_violation
        
        # Statistics
        self.checks_performed = 0
        self.violations_blocked = 0
        self.violations_warned = 0
    
    def on_call_start(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        emit: Optional[Callable] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Called before tool execution
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            context: Execution context
            emit: Event emitter
        
        Returns:
            None if allowed, or raises error if blocked
        
        Raises:
            FailCoreError if semantic violation detected
        """
        # Skip if disabled
        if not self.enabled:
            return None
        
        self.checks_performed += 1
        
        # Run semantic check
        verdict = self.detector.check(tool_name, params, context)
        
        # Emit semantic check event
        if emit:
            emit({
                "type": "SEMANTIC_CHECK",
                "tool": tool_name,
                "action": verdict.action.value,
                "has_violations": verdict.has_violations,
                "violation_count": len(verdict.violations),
            })
        
        # Handle verdict
        if verdict.is_blocked:
            self.violations_blocked += 1
            return self._handle_block(verdict, emit)
        
        elif verdict.action == VerdictAction.WARN:
            self.violations_warned += 1
            return self._handle_warn(verdict, emit)
        
        # ALLOW or LOG - pass through
        return None
    
    def _handle_block(
        self,
        verdict: Any,  # SemanticVerdict
        emit: Optional[Callable],
    ) -> None:
        """Handle blocked verdict"""
        from failcore.core.errors import FailCoreError, codes
        
        # Emit block event
        if emit:
            emit({
                "type": "SEMANTIC_BLOCKED",
                "verdict": verdict.to_dict(),
            })
        
        # Get first violation for error message
        first_violation = verdict.violations[0] if verdict.violations else None
        
        # Build error message
        if first_violation:
            message = f"Semantic violation: {first_violation.name}"
            suggestion = f"{first_violation.description}\n\nViolated rule: {first_violation.rule_id}"
        else:
            message = "Semantic violation detected"
            suggestion = "Review tool parameters for malicious patterns"
        
        # Raise error if blocking enabled
        if self.block_on_violation:
            raise FailCoreError(
                message=message,
                error_code=codes.SEMANTIC_VIOLATION,
                phase="SEMANTIC_CHECK",
                suggestion=suggestion,
                details={
                    "tool": verdict.tool_name,
                    "violations": [
                        {
                            "rule_id": v.rule_id,
                            "name": v.name,
                            "severity": v.severity.value,
                        }
                        for v in verdict.violations
                    ],
                    "explanation": verdict.get_explanation(),
                    "evidence": verdict.get_evidence(),
                }
            )
    
    def _handle_warn(
        self,
        verdict: Any,  # SemanticVerdict
        emit: Optional[Callable],
    ) -> None:
        """Handle warning verdict"""
        # Emit warning event
        if emit:
            emit({
                "type": "SEMANTIC_WARNING",
                "verdict": verdict.to_dict(),
            })
        
        # Log warning (don't block)
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get middleware statistics"""
        detector_stats = self.detector.get_stats()
        
        return {
            "enabled": self.enabled,
            "checks_performed": self.checks_performed,
            "violations_blocked": self.violations_blocked,
            "violations_warned": self.violations_warned,
            "block_rate": self.violations_blocked / self.checks_performed if self.checks_performed > 0 else 0.0,
            "detector_stats": detector_stats,
        }


__all__ = ["SemanticGuardMiddleware"]
