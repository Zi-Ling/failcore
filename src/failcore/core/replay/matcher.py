# failcore/core/replay/matcher.py
"""
Fingerprint matcher for replay hit/miss detection
"""

from typing import Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass


class MatchResult(str, Enum):
    """Match result types"""
    HIT = "HIT"  # Fingerprint matches, can inject output
    MISS = "MISS"  # Fingerprint doesn't match
    DIFF = "DIFF"  # Fingerprint matches but decision differs


@dataclass
class MatchInfo:
    """Match information"""
    result: MatchResult
    fingerprint_id: Optional[str] = None
    matched_step: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    diff_details: Optional[Dict[str, Any]] = None


class FingerprintMatcher:
    """
    Match current execution against historical trace
    
    Determines:
    - HIT: Can safely inject historical output
    - MISS: Must execute normally
    - DIFF: Can inject but decision differs (valuable signal!)
    """
    
    def match(
        self,
        current_fingerprint: Dict[str, Any],
        historical_step: Optional[Dict[str, Any]],
    ) -> MatchInfo:
        """
        Match current fingerprint against historical step
        
        Args:
            current_fingerprint: Current step's fingerprint
            historical_step: Historical step info from trace
        
        Returns:
            MatchInfo with result and details
        """
        if not historical_step:
            return MatchInfo(
                result=MatchResult.MISS,
                reason="No historical step found"
            )
        
        # Extract historical fingerprint
        hist_start = historical_step.get("start_event", {})
        hist_evt = hist_start.get("event", {})
        hist_step = hist_evt.get("step", {})
        hist_fingerprint = hist_step.get("fingerprint", {})
        
        if not hist_fingerprint:
            return MatchInfo(
                result=MatchResult.MISS,
                reason="Historical step has no fingerprint"
            )
        
        # Compare fingerprints
        curr_fp_id = current_fingerprint.get("id")
        hist_fp_id = hist_fingerprint.get("id")
        
        if curr_fp_id != hist_fp_id:
            return MatchInfo(
                result=MatchResult.MISS,
                fingerprint_id=curr_fp_id,
                reason=f"Fingerprint mismatch: {curr_fp_id} != {hist_fp_id}"
            )
        
        # Check input hashes
        curr_inputs = current_fingerprint.get("inputs", {})
        hist_inputs = hist_fingerprint.get("inputs", {})
        
        if curr_inputs.get("params_hash") != hist_inputs.get("params_hash"):
            return MatchInfo(
                result=MatchResult.MISS,
                fingerprint_id=curr_fp_id,
                reason="Input parameters differ"
            )
        
        # HIT - fingerprint matches
        return MatchInfo(
            result=MatchResult.HIT,
            fingerprint_id=curr_fp_id,
            matched_step=historical_step,
            reason="Fingerprint match"
        )
    
    def check_policy_diff(
        self,
        current_decision: tuple,  # (allowed, reason)
        historical_step: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Check if policy decision differs from historical (COUNTERFACTUAL)
        
        This re-evaluates policy with current rules against historical execution.
        This is the "what if rules changed" analysis.
        
        Returns:
            Diff details if differs, None otherwise
        """
        # Check if historical step was policy denied
        hist_policy_denied = False
        hist_policy_reason = None
        
        for evt in historical_step.get("other_events", []):
            evt_data = evt.get("event", {})
            if evt_data.get("type") == "POLICY_DENIED":
                hist_policy_denied = True
                policy_data = evt_data.get("data", {}).get("policy", {})
                hist_policy_reason = policy_data.get("reason")
                break
        
        # Also check end event
        end_evt = historical_step.get("end_event", {})
        if end_evt:
            end_data = end_evt.get("event", {}).get("data", {})
            result = end_data.get("result", {})
            if result.get("status") == "BLOCKED" and result.get("phase") == "policy":
                hist_policy_denied = True
                error = result.get("error", {})
                hist_policy_reason = error.get("message")
        
        current_allowed, current_reason = current_decision
        
        # COUNTERFACTUAL COMPARISON: Historical fact vs Current rule
        if hist_policy_denied and current_allowed:
            return {
                "type": "policy_now_allows",
                "historical": "denied",
                "current": "allowed",
                "historical_reason": hist_policy_reason,
                "current_reason": current_reason or "Policy now allows",
            }
        elif not hist_policy_denied and not current_allowed:
            return {
                "type": "policy_now_denies",
                "historical": "allowed",
                "current": "denied",
                "historical_reason": "Allowed",
                "current_reason": current_reason,
            }
        
        return None
    
    def check_output_diff(
        self,
        current_output: Any,
        historical_step: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Check if output normalization differs
        
        Returns:
            Diff details if differs, None otherwise
        """
        end_evt = historical_step.get("end_event", {})
        if not end_evt:
            return None
        
        end_data = end_evt.get("event", {}).get("data", {})
        payload = end_data.get("payload", {})
        hist_output = payload.get("output", {})
        hist_kind = hist_output.get("kind")
        
        # Get current kind
        if hasattr(current_output, 'kind'):
            curr_kind = current_output.kind.value
        elif isinstance(current_output, dict):
            curr_kind = current_output.get("kind")
        else:
            curr_kind = "unknown"
        
        if hist_kind != curr_kind:
            return {
                "type": "output_kind_differs",
                "historical": hist_kind,
                "current": curr_kind,
            }
        
        return None
