#failcore/core/validate/taint.py
"""
Taint Flow Validator

Lightweight validator that detects when sensitive data flows to high-risk sinks.

This validator is optional and should be enabled only when needed.
It provides a policy-driven way to detect taint flow violations.

NOTE: Taint tracking itself is provided via Context.state["taint_context"].
This validator only emits decisions when violations are detected.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from failcore.core.validate.validator import BaseValidator
from failcore.core.validate.contracts import Context, Decision, ValidatorConfig, RiskLevel
from failcore.core.guards.taint.tag import DataSensitivity, TaintTag
from failcore.core.guards.taint.context import TaintContext


class TaintFlowValidator(BaseValidator):
    """
    Taint Flow Validator
    
    Detects when sensitive data flows to high-risk sinks.
    
    This validator:
    - Reads taint context from Context.state["taint_context"]
    - Checks if tool is a high-risk sink
    - Detects tainted inputs
    - Emits decisions only for high-risk flows (configurable)
    
    NOTE: This is a lightweight validator. Full taint tracking is provided
    by TaintContext/TaintStore in Context.state.
    """
    
    @property
    def id(self) -> str:
        return "taint_flow"
    
    @property
    def domain(self) -> str:
        return "security"
    
    @property
    def config_schema(self) -> Optional[Dict[str, Any]]:
        """JSON schema for taint flow validator configuration"""
        return {
            "type": "object",
            "properties": {
                "min_sensitivity": {
                    "type": "string",
                    "enum": ["public", "internal", "confidential", "pii", "secret"],
                    "description": "Minimum sensitivity to report",
                    "default": "confidential",
                },
                "high_risk_sinks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of high-risk sink tools",
                },
                "require_explicit_sinks": {
                    "type": "boolean",
                    "description": "Only check explicitly listed sinks (default: false)",
                    "default": False,
                },
            },
        }
    
    @property
    def default_config(self) -> Dict[str, Any]:
        """Default taint flow validator configuration"""
        return {
            "min_sensitivity": "confidential",
            "high_risk_sinks": [],
            "require_explicit_sinks": False,
        }
    
    def evaluate(
        self,
        context: Context,
        config: Optional[ValidatorConfig] = None,
    ) -> List[Decision]:
        """
        Evaluate taint flow validation
        
        Args:
            context: Validation context (tool, params, state, etc.)
            config: Validator configuration
            
        Returns:
            List of Decision objects (empty if no violations)
        """
        decisions: List[Decision] = []
        
        # Get taint context from state
        taint_context = self._get_taint_context(context)
        if not taint_context:
            return decisions  # No taint context available
        
        # Get configuration
        cfg = self._get_config(config)
        tool_name = context.tool
        params = context.params or {}
        
        # Check if this is a high-risk sink
        if not self._is_high_risk_sink(tool_name, cfg, taint_context):
            return decisions  # Not a high-risk sink
        
        # Detect tainted inputs
        dependencies = context.state.get("dependencies", [])
        taint_tags: Set[TaintTag] = taint_context.detect_tainted_inputs(params, dependencies)
        
        if not taint_tags:
            return decisions  # No tainted inputs
        
        # Check minimum sensitivity threshold
        max_sensitivity = self._get_max_sensitivity(taint_tags)
        min_sensitivity = DataSensitivity(cfg.get("min_sensitivity", "confidential"))
        
        if not self._exceeds_threshold(max_sensitivity, min_sensitivity):
            return decisions  # Below threshold
        
        # Create decision
        code = f"FC_TAINT_FLOW_{max_sensitivity.value.upper()}_TO_SINK"
        message = (
            f"Taint flow detected: {max_sensitivity.value} data from "
            f"{len(taint_tags)} source(s) flowing to high-risk sink '{tool_name}'"
        )
        
        # Map sensitivity to risk level
        risk_level_map = {
            DataSensitivity.PUBLIC: RiskLevel.LOW,
            DataSensitivity.INTERNAL: RiskLevel.LOW,
            DataSensitivity.CONFIDENTIAL: RiskLevel.MEDIUM,
            DataSensitivity.PII: RiskLevel.HIGH,
            DataSensitivity.SECRET: RiskLevel.CRITICAL,
        }
        risk_level = risk_level_map.get(max_sensitivity, RiskLevel.MEDIUM)
        
        # Build evidence
        evidence: Dict[str, Any] = {
            "tool": tool_name,
            "sink_type": "high_risk",
            "sensitivity": max_sensitivity.value,
            "taint_sources": [tag.source.value for tag in taint_tags],
            "taint_count": len(taint_tags),
            "source_tools": list(set(tag.source_tool for tag in taint_tags)),
            "source_step_ids": list(set(tag.source_step_id for tag in taint_tags)),
        }
        
        # Create decision (always WARN for taint flow, not blocking)
        decision = Decision.warn(
            code=code,
            validator_id=self.id,
            message=message,
            evidence=evidence,
            risk_level=risk_level,
            tool=tool_name,
            step_id=context.step_id,
            remediation=(
                f"Review data flow from {len(taint_tags)} source(s) to sink '{tool_name}'. "
                f"Consider sanitizing {max_sensitivity.value} data before sending to external sinks."
            ),
        )
        
        decisions.append(decision)
        return decisions
    
    def _get_taint_context(self, context: Context) -> Optional[TaintContext]:
        """Get taint context from context state"""
        state = context.state or {}
        return state.get("taint_context")
    
    def _get_config(self, config: Optional[ValidatorConfig]) -> Dict[str, Any]:
        """Get merged configuration"""
        default = self.default_config
        if config and config.config:
            default.update(config.config)
        return default
    
    def _is_high_risk_sink(
        self,
        tool_name: str,
        config: Dict[str, Any],
        taint_context: TaintContext,
    ) -> bool:
        """Check if tool is a high-risk sink"""
        # Check explicit high-risk sinks list
        high_risk_sinks = config.get("high_risk_sinks", [])
        if high_risk_sinks:
            return tool_name in high_risk_sinks
        
        # If require_explicit_sinks is True, only check explicit list
        if config.get("require_explicit_sinks", False):
            return False
        
        # Use taint context to check if it's a sink
        if taint_context.is_sink_tool(tool_name):
            return True
        
        # Default: common high-risk sinks
        default_high_risk_sinks = [
            "send_email",
            "http_post",
            "http_get",
            "upload_file",
            "publish_message",
            "log_external",
        ]
        return tool_name in default_high_risk_sinks
    
    def _get_max_sensitivity(self, taint_tags: Set[TaintTag]) -> DataSensitivity:
        """Get maximum sensitivity from taint tags"""
        if not taint_tags:
            return DataSensitivity.INTERNAL
        
        # Sensitivity hierarchy
        hierarchy = {
            DataSensitivity.PUBLIC: 0,
            DataSensitivity.INTERNAL: 1,
            DataSensitivity.CONFIDENTIAL: 2,
            DataSensitivity.PII: 3,
            DataSensitivity.SECRET: 4,
        }
        
        max_level = max(hierarchy.get(tag.sensitivity, 1) for tag in taint_tags)
        for sensitivity, level in hierarchy.items():
            if level == max_level:
                return sensitivity
        
        return DataSensitivity.INTERNAL
    
    def _exceeds_threshold(
        self,
        sensitivity: DataSensitivity,
        min_sensitivity: DataSensitivity,
    ) -> bool:
        """Check if sensitivity exceeds threshold"""
        hierarchy = {
            DataSensitivity.PUBLIC: 0,
            DataSensitivity.INTERNAL: 1,
            DataSensitivity.CONFIDENTIAL: 2,
            DataSensitivity.PII: 3,
            DataSensitivity.SECRET: 4,
        }
        
        return hierarchy.get(sensitivity, 0) >= hierarchy.get(min_sensitivity, 0)


__all__ = ["TaintFlowValidator"]
