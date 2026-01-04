# failcore/web/services/decision_narrator.py
"""
Decision Narrator - translate machine decisions into human-readable explanations

Converts policy/guardian decisions into "why blocked / why passed" narratives
with evidence references.
"""

from typing import Dict, Any, List, Optional
from .replay_schema import StepFrame


class DecisionNarrator:
    """
    Narrates decisions made by Guardian/Policy engine
    
    Translates technical decisions into human-readable explanations.
    """
    
    def narrate(
        self,
        frame: StepFrame,
        policy_context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Generate decision narrative for a frame
        
        Args:
            frame: StepFrame to narrate
            policy_context: Optional policy context (rules, policies, etc.)
        
        Returns:
            Human-readable decision narrative, or None if no decision to narrate
        """
        if frame.status == "BLOCKED" or frame.status == "blocked":
            return self._narrate_blocked(frame, policy_context)
        elif frame.status == "OK":
            return self._narrate_passed(frame, policy_context)
        else:
            # PENDING, ERROR, etc. - no decision narrative
            return None
    
    def _narrate_blocked(self, frame: StepFrame, policy_context: Optional[Dict[str, Any]]) -> str:
        """Narrate why a step was blocked"""
        parts = []
        
        # Error code explanation
        if frame.error_code:
            error_explanation = self._explain_error_code(frame.error_code)
            if error_explanation:
                parts.append(error_explanation)
        
        # Policy/rule information
        if policy_context:
            rule_id = policy_context.get("rule_id")
            rule_name = policy_context.get("rule_name")
            policy_id = policy_context.get("policy_id")
            
            if rule_name:
                parts.append(f"Blocked by rule: {rule_name}")
            elif rule_id:
                parts.append(f"Blocked by rule: {rule_id}")
            
            if policy_id:
                parts.append(f"Policy: {policy_id}")
        
        # Field-level information
        if frame.anomalies:
            anomaly_fields = [a.get("field_path", "unknown") for a in frame.anomalies]
            if anomaly_fields:
                parts.append(f"Affected fields: {', '.join(set(anomaly_fields))}")
        
        # Default message if nothing specific
        if not parts:
            parts.append("Step was blocked by policy or budget limits")
        
        # Add evidence reference
        if frame.evidence:
            evidence_refs = [e.get("event_id") or e.get("seq") for e in frame.evidence if e.get("event_id") or e.get("seq")]
            if evidence_refs:
                parts.append(f"Evidence: events {', '.join(map(str, evidence_refs))}")
        
        return " | ".join(parts)
    
    def _narrate_passed(self, frame: StepFrame, policy_context: Optional[Dict[str, Any]]) -> str:
        """Narrate why a step passed"""
        parts = []
        
        # Risk assessment
        if frame.anomalies:
            severities = [a.get("severity", "low") for a in frame.anomalies]
            if "critical" in severities or "high" in severities:
                parts.append("Passed with high-risk anomalies")
            elif "medium" in severities:
                parts.append("Passed with medium-risk anomalies")
            else:
                parts.append("Passed with low-risk anomalies")
        else:
            parts.append("Passed all checks")
        
        # Budget status
        if frame.metrics:
            cost_metrics = frame.metrics.get("cost", {})
            if cost_metrics:
                incremental = cost_metrics.get("incremental", {})
                cost_usd = incremental.get("cost_usd", 0.0)
                if cost_usd > 0:
                    parts.append(f"Cost: ${cost_usd:.6f}")
        
        return " | ".join(parts) if parts else "Step completed successfully"
    
    def _explain_error_code(self, error_code: str) -> Optional[str]:
        """Explain error code in human-readable terms"""
        error_explanations = {
            "ECONOMIC_BUDGET_EXCEEDED": "Budget limit exceeded",
            "ECONOMIC_TOKEN_LIMIT": "Token limit exceeded",
            "ECONOMIC_BURN_RATE_EXCEEDED": "Burn rate limit exceeded",
            "BUDGET_COST_EXCEEDED": "Cost budget exceeded",
            "BUDGET_TOKENS_EXCEEDED": "Token budget exceeded",
            "BUDGET_API_CALLS_EXCEEDED": "API call limit exceeded",
            "BURN_RATE_EXCEEDED": "Spending rate too high",
            "POLICY_DENIED": "Policy rule denied",
        }
        
        # Try exact match first
        if error_code in error_explanations:
            return error_explanations[error_code]
        
        # Try partial match
        for code, explanation in error_explanations.items():
            if code in error_code:
                return explanation
        
        return None


# Singleton instance
_decision_narrator: Optional[DecisionNarrator] = None


def get_decision_narrator() -> DecisionNarrator:
    """Get decision narrator singleton"""
    global _decision_narrator
    if _decision_narrator is None:
        _decision_narrator = DecisionNarrator()
    return _decision_narrator


__all__ = ["DecisionNarrator", "get_decision_narrator"]
