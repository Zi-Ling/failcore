#failcore/core/validate/deduplication.py
"""
Decision Deduplication - Merge duplicate decisions from multiple validators

Prevents duplicate alerts when multiple validators detect the same issue.
Merges decisions by domain priority and marks duplicates.
"""

from __future__ import annotations

from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict

from .contracts import Decision, DecisionOutcome, RiskLevel


# Domain priority: higher priority wins, lower priority marked as duplicate
DOMAIN_PRIORITY = {
    "security": 100,  # Highest priority (path traversal, SSRF, etc.)
    "dlp": 80,        # DLP (sensitive data leakage)
    "semantic": 60,   # Semantic intent (dangerous combos, injection)
    "taint_flow": 40, # Taint flow tracking
    "drift": 20,      # Drift detection (lowest priority)
    "audit": 10,      # Audit-only validators
}


def deduplicate_decisions(decisions: List[Decision]) -> List[Decision]:
    """
    Deduplicate decisions by merging similar ones and marking duplicates
    
    Strategy:
    1. Group decisions by tool + similar evidence
    2. Within each group, keep highest priority domain decision
    3. Mark others as "duplicate_of" with reference to primary
    
    Args:
        decisions: List of decisions to deduplicate
        
    Returns:
        Deduplicated list of decisions
    """
    if not decisions:
        return decisions
    
    # Group decisions by tool and similar evidence signature
    groups = _group_similar_decisions(decisions)
    
    deduplicated = []
    seen_primary = set()
    
    for group in groups:
        if len(group) == 1:
            # No duplicates, keep as-is
            deduplicated.append(group[0])
            continue
        
        # Sort by domain priority (highest first)
        sorted_group = sorted(
            group,
            key=lambda d: DOMAIN_PRIORITY.get(d.validator_id.split("_")[0] if "_" in d.validator_id else d.validator_id, 50),
            reverse=True,
        )
        
        # Primary decision (highest priority)
        primary = sorted_group[0]
        deduplicated.append(primary)
        seen_primary.add(id(primary))
        
        # Mark others as duplicates (suppressed)
        for duplicate in sorted_group[1:]:
            # Add suppression metadata to evidence (explanatory metadata)
            duplicate.evidence = duplicate.evidence.copy()
            duplicate.evidence["suppressed_by"] = primary.code
            duplicate.evidence["suppression_reason"] = "duplicate_domain_lower_priority"
            duplicate.evidence["duplicate_of"] = primary.code  # Backward compatibility
            duplicate.evidence["duplicate_reason"] = (
                f"Same issue detected by {duplicate.validator_id}, "
                f"already covered by {primary.validator_id}"
            )
            duplicate.evidence["primary_code"] = primary.code
            duplicate.evidence["primary_validator"] = primary.validator_id
            duplicate.evidence["suppression_explanation"] = (
                f"Decision suppressed by {primary.validator_id} (domain priority: "
                f"{DOMAIN_PRIORITY.get(primary.validator_id.split('_')[0] if '_' in primary.validator_id else primary.validator_id, 50)} "
                f"> {DOMAIN_PRIORITY.get(duplicate.validator_id.split('_')[0] if '_' in duplicate.validator_id else duplicate.validator_id, 50)})"
            )
            
            # Change outcome to ALLOW (don't block twice)
            if duplicate.decision == DecisionOutcome.BLOCK:
                duplicate.decision = DecisionOutcome.ALLOW
                duplicate.message = f"[SUPPRESSED] {duplicate.message} (covered by {primary.validator_id})"
            
            deduplicated.append(duplicate)
    
    return deduplicated


def _group_similar_decisions(decisions: List[Decision]) -> List[List[Decision]]:
    """
    Group decisions that detect the same issue
    
    Groups by:
    - Same tool
    - Similar evidence (same pattern/rule/field)
    - Same risk level
    
    Returns:
        List of groups (each group is a list of similar decisions)
    """
    groups: Dict[str, List[Decision]] = defaultdict(list)
    
    for decision in decisions:
        # Create signature for grouping
        signature = _create_decision_signature(decision)
        groups[signature].append(decision)
    
    return list(groups.values())


def _create_decision_signature(decision: Decision) -> str:
    """
    Create signature for decision grouping
    
    Uses:
    - Tool name
    - Rule/pattern ID
    - Key evidence fields
    - Risk level
    """
    parts = [
        decision.tool or "unknown",
        decision.rule_id or decision.code,
        str(decision.risk_level.value),
    ]
    
    # Add key evidence fields
    evidence = decision.evidence or {}
    key_fields = ["pattern_name", "pattern_id", "rule_id", "field_path", "sensitivity"]
    for field in key_fields:
        if field in evidence:
            parts.append(f"{field}:{evidence[field]}")
    
    return "|".join(parts)


__all__ = ["deduplicate_decisions", "DOMAIN_PRIORITY"]
