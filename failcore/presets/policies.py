# failcore/presets/policies.py
"""
Policy Presets - Ready-to-use policy configurations

These presets provide common security and resource policies.
"""

import re
from typing import List, Tuple, Literal
from ..core.policy.policy import (
    Policy,
    ResourcePolicy,
    CostPolicy,
    CompositePolicy,
)

# ===== Helper: Rule-based matching (Suggestion #1) =====

RuleType = Literal["exact", "prefix", "regex"]
Rule = Tuple[RuleType, str, str]  # (type, pattern, reason)


def _match_rule(tool: str, rules: List[Rule]) -> Tuple[bool, str]:
    """
    Match tool against rules using exact/prefix/regex.
    
    Suggestion #1: Replace 'pattern in tool' with proper matching.
    
    Args:
        tool: Tool name
        rules: List of (rule_type, pattern, reason) tuples
    
    Returns:
        (matched, reason) tuple
    """
    tool_lower = tool.lower()
    
    for rule_type, pattern, reason in rules:
        if rule_type == "exact":
            if tool_lower == pattern.lower():
                return True, reason
        elif rule_type == "prefix":
            if tool_lower.startswith(pattern.lower()):
                return True, reason
        elif rule_type == "regex":
            if re.search(pattern, tool_lower):
                return True, reason
    
    return False, ""


def read_only() -> Policy:
    """
    Read-only policy preset - only allow read operations
    
    Deny all write operations using proper pattern matching.
    
    BEHAVIOR BOUNDARIES (Suggestion #2):
    - Policies currently match ONLY on tool name, NOT on parameters
    - Cannot differentiate based on dry_run=True or execution state
    - For parameter-aware policies, use custom Policy implementations
    
    Suggestion #1: Use exact/prefix/regex instead of 'pattern in tool'.
    
    Returns:
        Policy: Read-only policy
    
    Example:
        >>> from failcore import Session, presets
        >>> session = Session(policy=presets.read_only())
    """
    # Define deny rules with proper matching
    # 
    # IMPORTANT (Suggestion #1): Rule evaluation is FIRST-MATCH wins.
    # Rules are checked in order; intentional overlaps exist:
    # - Prefix rules catch structured tools (file.write, http.post)
    # - Regex rules catch legacy/unstructured tools (write_file, mkdir_unsafe)
    # 
    # Evaluation order: prefix first (specific), then regex (catch-all)
    deny_rules: List[Rule] = [
        # Prefix patterns (safer than substring matching)
        ("prefix", "file.write", "write operation"),
        ("prefix", "file.delete", "delete operation"),
        ("prefix", "file.create", "create operation"),
        ("prefix", "dir.create", "directory creation"),
        ("prefix", "dir.delete", "directory deletion"),
        ("prefix", "dir.remove", "directory removal"),
        ("prefix", "http.post", "HTTP POST"),
        ("prefix", "http.put", "HTTP PUT"),
        ("prefix", "http.delete", "HTTP DELETE"),
        ("prefix", "http.patch", "HTTP PATCH"),
        
        # Regex patterns for flexible matching (catch legacy/unstructured tools)
        ("regex", r".*(write|delete|remove|create|mkdir|rmdir).*", "write/delete operation"),
    ]
    
    class ReadOnlyPolicy:
        def allow(self, step, ctx):
            matched, operation = _match_rule(step.tool, deny_rules)
            
            if matched:
                # Suggestion #2: Include policy name in reason
                return False, f"[read_only] Write operation denied: {operation} ({step.tool})"
            
            return True, ""
    
    return ReadOnlyPolicy()


def safe_write(sandbox_root: str) -> Policy:
    """
    Safe write policy preset - file writes only allowed in sandbox directory
    
    IMPORTANT LIMITATIONS (Suggestion #3):
    ✔ Restricts path prefix to sandbox_root
    ✖ Does NOT prevent overwrites
    ✖ Does NOT validate symlink escapes
    ✖ Does NOT prevent ../ path traversal attacks
    
    For production use, combine with:
    - Path normalization/validation
    - Filesystem builtin (fs_safe)
    - Additional security policies
    
    Args:
        sandbox_root: Sandbox root directory path
    
    Returns:
        Policy: Safe write policy
    
    Example:
        >>> session = Session(
        ...     policy=presets.safe_write("/tmp/sandbox"),
        ...     sandbox="/tmp/sandbox"
        ... )
    """
    return ResourcePolicy(
        name="safe_write",
        allowed_paths=[sandbox_root]
    )


def dangerous_disabled() -> Policy:
    """
    Dangerous operations disabled preset - delete/overwrite/exec denied
    
    Deny all dangerous operations using proper pattern matching.
    
    Suggestion #1: Use regex patterns instead of substring matching.
    Suggestion #2: Include policy name in deny reason.
    
    Returns:
        Policy: Dangerous operations disabled policy
    
    Example:
        >>> session = Session(policy=presets.dangerous_disabled())
    """
    # Define dangerous operation rules
    dangerous_rules: List[Rule] = [
        # Regex patterns for dangerous operations
        ("regex", r".*(delete|remove|rm).*", "delete/remove operation"),
        ("regex", r".*overwrite.*", "overwrite operation"),
        ("regex", r".*(system|shell|exec|eval).*", "system/shell execution"),
        
        # Exact matches for common dangerous tools
        ("exact", "rm", "remove command"),
        ("exact", "unlink", "unlink operation"),
        ("exact", "rmdir", "remove directory"),
        ("exact", "exec", "exec command"),
        ("exact", "eval", "eval command"),
    ]
    
    class DangerousDisabledPolicy:
        def allow(self, step, ctx):
            matched, operation = _match_rule(step.tool, dangerous_rules)
            
            if matched:
                # Suggestion #2: Include policy name
                return False, f"[dangerous_disabled] Dangerous operation blocked: {operation} ({step.tool})"
            
            return True, ""
    
    return DangerousDisabledPolicy()


def cost_limit(
    max_steps: int = 1000,
    max_duration_seconds: float = 300.0
) -> Policy:
    """
    Cost limit policy preset
    
    Args:
        max_steps: Maximum number of steps (default 1000)
        max_duration_seconds: Maximum execution time in seconds (default 300)
    
    Returns:
        Policy: Cost limit policy
    
    Example:
        >>> session = Session(policy=presets.cost_limit(max_steps=100))
    """
    return CostPolicy(
        max_total_steps=max_steps,
        max_duration_seconds=max_duration_seconds
    )


def combine_policies(*policies: Policy) -> Policy:
    """
    Combine multiple policies
    
    All policies must pass for execution to be allowed.
    
    EVALUATION SEMANTICS (Suggestion #5):
    - Policies are evaluated in the order provided
    - First failure wins (short-circuit evaluation)
    - Deny reason comes from the first failing policy
    - For debugging, check policy order if results seem unexpected
    
    Args:
        *policies: List of policies to combine
    
    Returns:
        Policy: Combined policy
    
    Example:
        >>> policy = presets.combine_policies(
        ...     presets.read_only(),       # Checked first
        ...     presets.cost_limit(max_steps=100)  # Checked second
        ... )
        >>> session = Session(policy=policy)
    """
    return CompositePolicy(
        name="combined",
        policies=list(policies)
    )


__all__ = [
    "read_only",
    "safe_write",
    "dangerous_disabled",
    "cost_limit",
    "combine_policies",
]

