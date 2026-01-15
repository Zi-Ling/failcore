"""
DLP Guard Validator

Data Loss Prevention validator that detects sensitive data leakage at tool call boundaries.

This validator integrates with the taint tracking system to detect when sensitive data
flows from source tools to sink tools, and applies DLP policies based on data sensitivity.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from failcore.core.guards.dlp.sanitizer import StructuredSanitizer
from failcore.core.validate.validator import BaseValidator
from failcore.core.validate.contracts import Context, Decision, ValidatorConfig, RiskLevel
from failcore.core.rules import RuleRegistry, RuleCategory
from failcore.core.guards.dlp import PatternCategory  # Legacy compatibility
from failcore.core.guards.dlp.policies import DLPAction, DLPPolicy, PolicyMatrix
from failcore.core.guards.taint.tag import DataSensitivity, TaintTag
from failcore.core.guards.taint.context import TaintContext
from failcore.core.guards.decision import (
    dlp_policy_to_decision,
    data_sensitivity_to_risk_level,
)


class DLPGuardValidator(BaseValidator):
    """
    DLP Guard Validator
    
    Detects sensitive data leakage by:
    1. Checking if tool is a data sink
    2. Detecting tainted inputs (from taint context)
    3. Scanning parameters for sensitive patterns
    4. Applying DLP policy based on sensitivity
    5. Returning unified Decision objects
    """
    
    def __init__(
        self,
        taint_context: Optional[TaintContext] = None,
        rule_registry: Optional[RuleRegistry] = None,
        sanitizer: Optional[StructuredSanitizer] = None,
    ):
        """
        Initialize DLP guard validator
        
        Args:
            taint_context: Taint tracking context (optional, will create if None)
            pattern_registry: DLP pattern registry (optional, will create if None)
            sanitizer: Structured sanitizer (optional, will create if None)
        """
        self.taint_context = taint_context
        # Load default DLP ruleset if not provided
        if rule_registry is None:
            from failcore.infra.rulesets import FileSystemLoader
            from failcore.core.rules.loader import CompositeLoader
            from pathlib import Path
            
            default_path = Path(__file__).parent.parent.parent.parent.parent.parent / "config" / "rulesets" / "default"
            loader = CompositeLoader([
                FileSystemLoader(Path.home() / ".failcore" / "rulesets"),
                FileSystemLoader(default_path),
            ])
            rule_registry = RuleRegistry(loader)
            rule_registry.load_ruleset("dlp")
        
        self.rule_registry = rule_registry
        self.sanitizer = sanitizer
    
    @property
    def id(self) -> str:
        return "dlp_guard"
    
    @property
    def domain(self) -> str:
        return "security"
    
    @property
    def config_schema(self) -> Optional[Dict[str, Any]]:
        """JSON schema for DLP validator configuration"""
        return {
            "type": "object",
            "properties": {
                "strict_mode": {
                    "type": "boolean",
                    "description": "Use strict policy matrix (default: true)",
                    "default": True,
                },
                "min_severity": {
                    "type": "integer",
                    "description": "Minimum pattern severity to report (1-10)",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 1,
                },
                "scan_params": {
                    "type": "boolean",
                    "description": "Scan tool parameters for sensitive patterns",
                    "default": True,
                },
                "use_taint_tracking": {
                    "type": "boolean",
                    "description": "Use taint tracking context (if available)",
                    "default": True,
                },
                "source_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tools that produce sensitive data",
                },
                "sink_tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of tools that consume data (potential leaks)",
                },
            },
        }
    
    @property
    def default_config(self) -> Dict[str, Any]:
        """Default DLP validator configuration"""
        return {
            "strict_mode": True,
            "min_severity": 1,
            "scan_params": True,
            "use_taint_tracking": True,
        }
    
    def evaluate(
        self,
        context: Context,
        config: Optional[ValidatorConfig] = None,
    ) -> List[Decision]:
        """
        Evaluate DLP validation
        
        Args:
            context: Validation context (tool, params, etc.)
            config: Validator configuration
            
        Returns:
            List of Decision objects (empty if no violations)
        """
        decisions: List[Decision] = []
        
        # Get configuration
        cfg = self._get_config(config)
        tool_name = context.tool
        params = context.params or {}
        
        # Check if this is a sink tool
        if not self._is_sink_tool(tool_name, cfg):
            return decisions  # Not a sink, no DLP check needed
        
        # Get taint context from context state (if available)
        taint_context = self._get_taint_context(context)
        
        # Detect tainted inputs (if taint tracking enabled)
        taint_tags: Set[TaintTag] = set()
        if cfg.get("use_taint_tracking", True) and taint_context:
            dependencies = context.state.get("dependencies", [])
            taint_tags = taint_context.detect_tainted_inputs(params, dependencies)
        
        # Scan parameters for sensitive patterns (if enabled)
        # Use scanners interface to share results with enricher
        pattern_matches = []
        if cfg.get("scan_params", True):
            # Get scan cache from context state (must be run-scoped)
            scan_cache = context.state.get("scan_cache")
            if scan_cache is None:
                # Create cache if not available (fallback)
                from failcore.core.guards.cache import ScanCache
                run_id = context.session_id or context.step_id or "validator_fallback"
                scan_cache = ScanCache(run_id=run_id)
                # Store in context for reuse
                context.state["scan_cache"] = scan_cache
            
            # Use scanners interface (this is the ONLY way to scan)
            from failcore.core.guards.scanners import scan_dlp
            
            # Call scanner (will check cache first, then scan if needed)
            scan_result = scan_dlp(
                payload=params,
                cache=scan_cache,
                step_id=context.step_id,
                rule_registry=self.rule_registry,
            )
            
            # Extract matches from ScanResult
            results = scan_result.results
            matches = results.get("matches", [])
            
            # Convert to pattern_matches format (for compatibility with existing code)
            from types import SimpleNamespace
            for match in matches:
                pattern_obj = SimpleNamespace(
                    name=match.get("pattern", "unknown"),
                    category=SimpleNamespace(value=match.get("category", "unknown")),
                    severity=match.get("severity", 0),
                )
                pattern_matches.append((match.get("matched_text", ""), pattern_obj))
            
            # Add cache info to evidence
            evidence["scan_cache_hit"] = scan_result.cache_key.payload_fingerprint is not None
            evidence["scan_hash"] = scan_result.cache_key.payload_fingerprint
        
        # If no taint tags and no pattern matches, no violation
        if not taint_tags and not pattern_matches:
            return decisions
        
        # Determine maximum sensitivity
        max_sensitivity = self._get_max_sensitivity(taint_tags, pattern_matches)
        
        # Create policy matrix
        policy_matrix = PolicyMatrix(strict_mode=cfg.get("strict_mode", True))
        
        # Get policy for this sensitivity level
        policy = policy_matrix.get_policy(max_sensitivity)
        
        # Build evidence
        evidence: Dict[str, Any] = {
            "tool": tool_name,
            "sensitivity": max_sensitivity.value,
            "taint_sources": [tag.source.value for tag in taint_tags] if taint_tags else [],
            "taint_count": len(taint_tags),
        }
        
        # Add pattern matches to evidence
        if pattern_matches:
            evidence["pattern_matches"] = [
                {
                    "pattern_name": pattern.name,
                    "pattern_category": pattern.category.value,
                    "severity": pattern.severity,
                }
                for _, pattern in pattern_matches
            ]
        
        # Convert policy to decision
        code = f"FC_DLP_{max_sensitivity.value.upper()}_DETECTED"
        message = f"DLP: {max_sensitivity.value} data detected in {tool_name} parameters"
        
        decision = dlp_policy_to_decision(
            policy=policy,
            validator_id=self.id,
            code=code,
            message=message,
            evidence=evidence,
            pattern_id=pattern_matches[0][1].name if pattern_matches else None,
            sensitivity=max_sensitivity,
        )
        
        # Add tool and step_id to decision
        decision.tool = tool_name
        decision.step_id = context.step_id
        
        decisions.append(decision)
        
        return decisions
    
    def _get_config(self, config: Optional[ValidatorConfig]) -> Dict[str, Any]:
        """Get merged configuration"""
        default = self.default_config
        if config and config.config:
            default.update(config.config)
        return default
    
    def _get_taint_context(self, context: Context) -> Optional[TaintContext]:
        """Get taint context from context state or use instance context"""
        # Try to get from context state first
        state = context.state or {}
        if "taint_context" in state:
            return state["taint_context"]
        
        # Fall back to instance context
        return self.taint_context
    
    def _is_sink_tool(self, tool_name: str, config: Dict[str, Any]) -> bool:
        """Check if tool is a data sink"""
        # Check explicit sink list in config
        sink_tools = config.get("sink_tools", [])
        if sink_tools:
            return tool_name in sink_tools
        
        # Use taint context if available
        taint_context = self.taint_context
        if taint_context:
            return taint_context.is_sink_tool(tool_name)
        
        # Default: common sink tools
        default_sinks = [
            "send_email",
            "http_post",
            "http_get",
            "upload_file",
            "publish_message",
            "log_external",
            "write_file",  # External file writes
        ]
        return tool_name in default_sinks
    
    def _scan_params_for_patterns(
        self,
        params: Dict[str, Any],
        config: Dict[str, Any],
    ) -> List[tuple[str, Any]]:
        """
        Scan parameters for sensitive patterns
        
        Args:
            params: Tool parameters
            config: Validator configuration
            
        Returns:
            List of (matched_text, pattern) tuples
        """
        matches = []
        min_severity = config.get("min_severity", 1)
        
        # Recursively scan all string values using scan_dlp
        from failcore.core.guards.scanners import scan_dlp
        from failcore.core.guards.cache import ScanCache
        
        # Create temporary cache for scanning
        temp_cache = ScanCache(run_id="validator_scan")
        
        def scan_value(value: Any) -> None:
            if isinstance(value, str):
                # Use scan_dlp for scanning
                scan_result = scan_dlp(
                    payload=value,
                    cache=temp_cache,
                    rule_registry=self.rule_registry,
                )
                # Convert results to matches format
                for match in scan_result.results.get("matches", []):
                    from types import SimpleNamespace
                    pattern_obj = SimpleNamespace(
                        name=match.get("pattern", "unknown"),
                        category=SimpleNamespace(value=match.get("category", "unknown")),
                        severity=match.get("severity", 0),
                    )
                    if match.get("severity", 0) >= min_severity:
                        matches.append((match.get("matched_text", ""), pattern_obj))
            elif isinstance(value, dict):
                for v in value.values():
                    scan_value(v)
            elif isinstance(value, list):
                for item in value:
                    scan_value(item)
        
        for value in params.values():
            scan_value(value)
        
        return matches
    
    def _get_max_sensitivity(
        self,
        taint_tags: Set[TaintTag],
        pattern_matches: List[tuple[str, Any]],
    ) -> DataSensitivity:
        """Determine maximum sensitivity from taint tags and pattern matches"""
        sensitivities = []
        
        # Get sensitivity from taint tags
        if taint_tags:
            for tag in taint_tags:
                sensitivities.append(tag.sensitivity)
        
        # Infer sensitivity from pattern matches
        if pattern_matches:
            for _, pattern in pattern_matches:
                # Map pattern category to sensitivity
                category_value = pattern.category.value if hasattr(pattern.category, 'value') else str(pattern.category)
                if category_value in ("dlp.api_key", "dlp.secret"):
                    sensitivities.append(DataSensitivity.SECRET)
                elif category_value == "dlp.pii":
                    sensitivities.append(DataSensitivity.PII)
                elif category_value == "dlp.payment":
                    sensitivities.append(DataSensitivity.CONFIDENTIAL)
                else:
                    sensitivities.append(DataSensitivity.INTERNAL)
        
        # Return maximum sensitivity
        if not sensitivities:
            return DataSensitivity.INTERNAL
        
        # Sensitivity hierarchy
        hierarchy = {
            DataSensitivity.PUBLIC: 0,
            DataSensitivity.INTERNAL: 1,
            DataSensitivity.CONFIDENTIAL: 2,
            DataSensitivity.PII: 3,
            DataSensitivity.SECRET: 4,
        }
        
        max_level = max(hierarchy.get(s, 1) for s in sensitivities)
        for sensitivity, level in hierarchy.items():
            if level == max_level:
                return sensitivity
        
        return DataSensitivity.INTERNAL


__all__ = ["DLPGuardValidator"]
