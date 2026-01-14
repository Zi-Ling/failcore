# failcore/core/rules/models.py
"""
Unified Rule Models

Defines common rule models used across all guard modules (DLP, Semantic, Effects, Taint, Drift)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Pattern
from enum import Enum
import re


class RuleSeverity(str, Enum):
    """Rule severity levels"""
    CRITICAL = "critical"  # Always block
    HIGH = "high"          # Block by default
    MEDIUM = "medium"      # Warn
    LOW = "low"            # Log only


class RuleCategory(str, Enum):
    """Rule categories"""
    # DLP categories
    DLP_API_KEY = "dlp.api_key"
    DLP_SECRET = "dlp.secret"
    DLP_PII = "dlp.pii"
    DLP_PAYMENT = "dlp.payment"
    
    # Semantic categories
    SEMANTIC_SECRET_LEAKAGE = "semantic.secret_leakage"
    SEMANTIC_INJECTION = "semantic.injection"
    SEMANTIC_DANGEROUS_COMBO = "semantic.dangerous_combo"
    SEMANTIC_PATH_TRAVERSAL = "semantic.path_traversal"
    
    # Effect categories
    EFFECT_FILESYSTEM = "effect.filesystem"
    EFFECT_NETWORK = "effect.network"
    EFFECT_EXEC = "effect.exec"
    
    # Taint categories
    TAINT_SOURCE = "taint.source"
    TAINT_SINK = "taint.sink"
    TAINT_PROPAGATION = "taint.propagation"
    
    # Drift categories
    DRIFT_VALUE = "drift.value_changed"
    DRIFT_MAGNITUDE = "drift.magnitude_changed"
    DRIFT_DOMAIN = "drift.domain_changed"


class RuleAction(str, Enum):
    """Actions to take when rule matches"""
    BLOCK = "block"                    # Block execution
    SANITIZE = "sanitize"              # Sanitize data
    WARN = "warn"                      # Log warning
    REQUIRE_APPROVAL = "require_approval"  # Require human approval
    ALLOW = "allow"                    # Allow (for whitelist rules)
    LOG = "log"                        # Log only


@dataclass
class RuleMetadata:
    """Rule metadata for tracking and verification"""
    source: str = "builtin"  # builtin, community, local, custom
    version: str = "1.0.0"
    author: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    signature: Optional[str] = None  # SHA256 checksum
    trust_level: str = "trusted"  # trusted, untrusted, unknown
    tags: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)


@dataclass
class Pattern:
    """
    Pattern definition for DLP/Semantic rules
    
    Can be regex, keyword, or custom detector
    """
    pattern_type: str  # "regex", "keyword", "custom"
    value: Any  # regex string, keyword string, or detector function
    flags: int = 0  # regex flags
    compiled: Optional[Pattern] = field(default=None, repr=False)
    
    def __post_init__(self):
        """Compile regex patterns"""
        if self.pattern_type == "regex" and isinstance(self.value, str):
            try:
                self.compiled = re.compile(self.value, self.flags)
            except re.error:
                # Invalid regex, will be handled by validator
                pass
    
    def match(self, text: str) -> bool:
        """Check if pattern matches text"""
        if self.pattern_type == "regex" and self.compiled:
            return bool(self.compiled.search(text))
        elif self.pattern_type == "keyword" and isinstance(self.value, str):
            return self.value.lower() in text.lower()
        return False


@dataclass
class Rule:
    """
    Unified rule model
    
    Used across all guard modules with module-specific fields in `config`
    """
    # Core identification
    rule_id: str
    name: str
    category: RuleCategory
    severity: RuleSeverity
    
    # Rule specification
    description: str
    patterns: List[Pattern] = field(default_factory=list)
    detector: Optional[Callable[[str, Dict[str, Any]], bool]] = field(default=None, repr=False)
    
    # Action
    action: RuleAction = RuleAction.WARN
    
    # Metadata
    metadata: RuleMetadata = field(default_factory=RuleMetadata)
    enabled: bool = True
    
    # Module-specific config
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Examples
    examples: List[Dict[str, Any]] = field(default_factory=list)
    
    # Performance hints
    false_positive_rate: float = 0.0
    performance_impact: str = "low"  # low, medium, high
    
    def check(self, tool_name: str, params: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if rule matches
        
        Args:
            tool_name: Tool name
            params: Tool parameters
            context: Optional context
        
        Returns:
            True if rule matches
        """
        if not self.enabled:
            return False
        
        # Use custom detector if provided
        if self.detector:
            try:
                return self.detector(tool_name, params)
            except Exception:
                # Fail open - don't block on detector errors
                return False
        
        # Use patterns if no detector
        if self.patterns:
            # Convert params to string for pattern matching
            text = self._params_to_text(params)
            return any(pattern.match(text) for pattern in self.patterns)
        
        return False
    
    def _params_to_text(self, params: Dict[str, Any]) -> str:
        """Convert params to searchable text"""
        import json
        try:
            return json.dumps(params, ensure_ascii=False)
        except Exception:
            return str(params)


@dataclass
class RuleSet:
    """
    Collection of rules
    
    Represents a loadable ruleset (e.g., dlp.yml, semantic.yml)
    """
    name: str
    version: str
    description: str
    rules: List[Rule]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get rule by ID"""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    def get_rules_by_category(self, category: RuleCategory) -> List[Rule]:
        """Get all rules in a category"""
        return [r for r in self.rules if r.category == category]
    
    def get_enabled_rules(self) -> List[Rule]:
        """Get all enabled rules"""
        return [r for r in self.rules if r.enabled]


@dataclass
class PolicyMatrix:
    """
    Policy matrix for DLP
    
    Maps data sensitivity to actions
    """
    sensitivity_actions: Dict[str, RuleAction] = field(default_factory=dict)
    strict_mode: bool = True
    
    def get_action(self, sensitivity: str) -> RuleAction:
        """Get action for sensitivity level"""
        return self.sensitivity_actions.get(sensitivity, RuleAction.WARN)


@dataclass
class ThresholdConfig:
    """
    Threshold configuration for Drift
    """
    magnitude_threshold_medium: float = 2.0
    magnitude_threshold_high: float = 5.0
    ignore_fields: List[str] = field(default_factory=list)
    tool_specific_ignore: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ToolMapping:
    """
    Tool to effect/taint mapping
    
    Used by Effect and Taint modules
    """
    tool_patterns: List[str] = field(default_factory=list)  # regex patterns
    keywords: List[str] = field(default_factory=list)  # keyword matches
    exact_matches: List[str] = field(default_factory=list)  # exact tool names
    
    def matches(self, tool_name: str) -> bool:
        """Check if tool matches this mapping"""
        # Exact match first
        if tool_name in self.exact_matches:
            return True
        
        # Keyword match
        tool_lower = tool_name.lower()
        if any(kw in tool_lower for kw in self.keywords):
            return True
        
        # Regex match
        for pattern_str in self.tool_patterns:
            try:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                if pattern.search(tool_name):
                    return True
            except re.error:
                continue
        
        return False


__all__ = [
    "RuleSeverity",
    "RuleCategory",
    "RuleAction",
    "RuleMetadata",
    "Pattern",
    "Rule",
    "RuleSet",
    "PolicyMatrix",
    "ThresholdConfig",
    "ToolMapping",
]
