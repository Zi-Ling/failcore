"""
Semantic Intent Guard Validator

High-confidence semantic validation for tool calls.
Only covers extremely rare, 100% malicious scenarios:
- Dangerous command combinations
- Parameter pollution/injection
- Intent-based security violations

NOTE: This validator focuses on INTENT-based/combinatorial risks.
For sensitive data leakage, use DLP validator.
For path traversal, use security_path_traversal validator.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from failcore.core.validate.validator import BaseValidator
from failcore.core.validate.contracts import Context, Decision, ValidatorConfig, RiskLevel
from failcore.core.rules import (
    RuleCategory,
    RuleSeverity,
    RuleRegistry,
    RuleEngine,
)
from failcore.core.guards.semantic.detectors import SemanticDetector
from failcore.core.guards.semantic.verdict import SemanticVerdict
from failcore.core.guards.semantic.parsers import (
    ShellParser,
    SQLParser,
    URLParser,
    PathParser,
    PayloadParser,
)
from failcore.core.guards.decision import semantic_verdict_to_decision


class SemanticIntentValidator(BaseValidator):
    """
    Semantic Intent Guard Validator
    
    Detects malicious patterns using semantic rules:
    - Dangerous command combinations (rm -rf /, fork bombs)
    - Parameter pollution (SQL injection, XSS, code injection)
    - Intent-based violations (not data leakage, not path traversal)
    
    Responsibility boundaries:
    - Semantic: Intent/combinatorial risks
    - DLP: Sensitive data leakage
    - Security validators: Path traversal, SSRF, etc.
    """
    
    def __init__(
        self,
        registry: Optional[RuleRegistry] = None,
    ):
        """
        Initialize semantic intent validator
        
        Args:
            registry: Rule registry (optional, will create if None)
        """
        self.registry = registry or RuleRegistry()
        self.detector = SemanticDetector(rule_registry=self.registry)
        
        # Initialize parsers for deterministic parsing
        self.shell_parser = ShellParser()
        self.sql_parser = SQLParser()
        self.url_parser = URLParser()
        self.path_parser = PathParser()
        self.payload_parser = PayloadParser()
    
    @property
    def id(self) -> str:
        return "semantic_intent"
    
    @property
    def domain(self) -> str:
        return "security"
    
    @property
    def config_schema(self) -> Optional[Dict[str, Any]]:
        """JSON schema for semantic validator configuration"""
        return {
            "type": "object",
            "properties": {
                "min_severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Minimum severity to enforce",
                    "default": "high",
                },
                "enabled_categories": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "secret_leakage",
                            "param_pollution",
                            "dangerous_combo",
                            "path_traversal",
                            "injection",
                        ],
                    },
                    "description": "List of enabled rule categories (None = all)",
                },
                "block_on_violation": {
                    "type": "boolean",
                    "description": "Block execution on violation (default: true)",
                    "default": True,
                },
            },
        }
    
    @property
    def default_config(self) -> Dict[str, Any]:
        """Default semantic validator configuration"""
        return {
            "min_severity": "high",
            "enabled_categories": None,  # All categories
            "block_on_violation": True,
        }
    
    def evaluate(
        self,
        context: Context,
        config: Optional[ValidatorConfig] = None,
    ) -> List[Decision]:
        """
        Evaluate semantic validation
        
        Args:
            context: Validation context (tool, params, etc.)
            config: Validator configuration
            
        Returns:
            List of Decision objects (empty if no violations)
        """
        # Get configuration
        cfg = self._get_config(config)
        tool_name = context.tool
        params = context.params or {}
        
        # Parse parameters deterministically (create unified AST)
        parsed_data = self._parse_parameters(tool_name, params)
        
        # Update detector configuration
        min_severity = RuleSeverity(cfg.get("min_severity", "high"))
        enabled_categories = cfg.get("enabled_categories")
        
        # Create detector with config
        detector = SemanticDetector(
            rule_registry=self.registry,
            min_severity=min_severity,
            enabled_categories=enabled_categories,
        )
        
        # Check tool call (detector can use parsed_data for structured evaluation)
        verdict = detector.check(
            tool_name=tool_name,
            params=params,
            context=context.to_dict(),
        )
        
        # Convert verdict to decisions
        decisions = semantic_verdict_to_decision(
            verdict=verdict,
            validator_id=self.id,
        )
        
        # Add parsed data to evidence for explainability
        for decision in decisions:
            decision.tool = tool_name
            decision.step_id = context.step_id
            # Add parsed structure to evidence
            if parsed_data:
                decision.evidence["parsed_structure"] = parsed_data
        
        return decisions
    
    def _parse_parameters(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Parse parameters deterministically into unified AST
        
        Returns:
            Dict with parsed structures (shell_ast, sql_features, url_norm, etc.)
        """
        parsed = {}
        
        # Parse each parameter value
        for key, value in params.items():
            if not isinstance(value, str):
                continue
            
            # Shell command parsing
            if tool_name in ("run_command", "exec_shell", "bash", "shell_exec"):
                try:
                    shell_ast = self.shell_parser.tokenize(value)
                    parsed[f"{key}_shell_ast"] = shell_ast
                except Exception:
                    pass
            
            # SQL parsing
            if "sql" in key.lower() or "query" in key.lower():
                try:
                    sql_features = self.sql_parser.extract_keywords(value)
                    parsed[f"{key}_sql_features"] = sql_features
                except Exception:
                    pass
            
            # URL parsing
            if "url" in key.lower() or "uri" in key.lower() or "endpoint" in key.lower():
                try:
                    url_norm = self.url_parser.parse(value)
                    parsed[f"{key}_url_norm"] = url_norm
                except Exception:
                    pass
            
            # Path parsing
            if "path" in key.lower() or "file" in key.lower():
                try:
                    path_norm = self.path_parser.normalize(value)
                    parsed[f"{key}_path_norm"] = path_norm
                except Exception:
                    pass
            
            # JSON payload parsing
            if value.strip().startswith("{") or value.strip().startswith("["):
                try:
                    payload_parsed = self.payload_parser.parse_json(value)
                    if payload_parsed.get("valid"):
                        parsed[f"{key}_payload"] = payload_parsed
                except Exception:
                    pass
        
        return parsed
    
    def _get_config(self, config: Optional[ValidatorConfig]) -> Dict[str, Any]:
        """Get merged configuration"""
        default = self.default_config
        if config and config.config:
            default.update(config.config)
        return default


__all__ = ["SemanticIntentValidator"]
