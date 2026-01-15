# failcore/core/runtime/capability.py
"""
Runtime Capability Descriptor

Read-only view of what modules are enabled and how.
This is for observability/debugging, NOT for runtime decisions.

Capabilities come from Runtime/Registry (factual state), not Config (desired state).
"""

from typing import Dict, Any, Literal, Optional
from dataclasses import dataclass, field

from failcore.config.modules import (
    DLPConfig,
    SemanticConfig,
    EffectsConfig,
    TaintConfig,
    DriftConfig,
)
from failcore.core.rules import RuleRegistry


@dataclass(frozen=True)
class ModuleCapability:
    """Module capability descriptor"""
    status: Literal["enabled", "disabled"]
    mode: str = ""
    rules_count: int = 0
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeCapabilities:
    """
    Runtime capabilities - read-only view of module states.
    
    This is for:
    - UI display
    - Report generation
    - Audit logs
    - Debugging
    
    NOT for:
    - Runtime decision making (use Engine instances directly)
    
    Note: Capabilities come from runtime/registry (factual state),
    not from config (desired state).
    """
    
    dlp: ModuleCapability
    semantic: ModuleCapability
    effects: ModuleCapability
    taint: ModuleCapability
    drift: ModuleCapability
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "dlp": {
                "status": self.dlp.status,
                "mode": self.dlp.mode,
                "rules_count": self.dlp.rules_count,
                "config": self.dlp.config,
            },
            "semantic": {
                "status": self.semantic.status,
                "rules_count": self.semantic.rules_count,
                "config": self.semantic.config,
            },
            "effects": {
                "status": self.effects.status,
                "mode": self.effects.mode,
                "rules_count": self.effects.rules_count,
                "config": self.effects.config,
            },
            "taint": {
                "status": self.taint.status,
                "rules_count": self.taint.rules_count,
                "config": self.taint.config,
            },
            "drift": {
                "status": self.drift.status,
                "mode": "analysis_only" if self.drift.mode == "analysis_only" else "enforcement",
                "config": self.drift.config,
            },
        }
    
    def __str__(self) -> str:
        """Human-readable representation"""
        lines = ["Runtime Capabilities:"]
        for name, cap in [
            ("DLP", self.dlp),
            ("Semantic", self.semantic),
            ("Effects", self.effects),
            ("Taint", self.taint),
            ("Drift", self.drift),
        ]:
            if cap.status == "enabled":
                mode_str = f" ({cap.mode})" if cap.mode else ""
                rules_str = f" [{cap.rules_count} rules]" if cap.rules_count > 0 else " [no rules]"
                lines.append(f"  {name}: enabled{mode_str}{rules_str}")
            else:
                lines.append(f"  {name}: disabled")
        return "\n".join(lines)


def build_capabilities(
    dlp_engine,
    semantic_engine,
    effects_engine,
    taint_engine,
    drift_engine,
    dlp_config: Optional[DLPConfig] = None,
    semantic_config: Optional[SemanticConfig] = None,
    effects_config: Optional[EffectsConfig] = None,
    taint_config: Optional[TaintConfig] = None,
    drift_config: Optional[DriftConfig] = None,
    rule_registry: Optional[RuleRegistry] = None,
) -> RuntimeCapabilities:
    """
    Build runtime capabilities descriptor from engines/registry (factual state).
    
    Args:
        dlp_engine: DLP engine instance (Real or NoOp)
        semantic_engine: Semantic engine instance (Real or NoOp)
        effects_engine: Effects engine instance (Real or NoOp)
        taint_engine: Taint engine instance (Real or NoOp)
        drift_engine: Drift engine instance (Real or NoOp)
        dlp_config: Optional DLP config (for mode/config display only)
        semantic_config: Optional Semantic config (for display only)
        effects_config: Optional Effects config (for display only)
        taint_config: Optional Taint config (for display only)
        drift_config: Optional Drift config (for display only)
        rule_registry: Rule registry to get rule counts (factual state)
    
    Returns:
        RuntimeCapabilities instance (frozen, read-only)
    
    Note:
        Capabilities MUST reflect factual runtime state (engine/registry),
        NOT config.enabled (desired state).
        
        This distinguishes:
        - "enabled=true, rules=0" (module enabled but no rules loaded)
        - "enabled=false" (module not registered, NoOp engine)
    """
    # Determine status from engine type (factual state, not config)
    from failcore.core.guards.dlp.engine import NoOpDlpEngine
    from failcore.core.guards.semantic.engine import NoOpSemanticEngine
    from failcore.core.guards.effects.engine import NoOpEffectsEngine
    from failcore.core.guards.taint.engine import NoOpTaintEngine
    from failcore.core.replay.drift.engine import NoOpDriftEngine
    
    dlp_status = "disabled" if isinstance(dlp_engine, NoOpDlpEngine) else "enabled"
    semantic_status = "disabled" if isinstance(semantic_engine, NoOpSemanticEngine) else "enabled"
    effects_status = "disabled" if isinstance(effects_engine, NoOpEffectsEngine) else "enabled"
    taint_status = "disabled" if isinstance(taint_engine, NoOpTaintEngine) else "enabled"
    drift_status = "disabled" if isinstance(drift_engine, NoOpDriftEngine) else "enabled"
    
    # Get rule counts from registry (factual state)
    dlp_rules = 0
    semantic_rules = 0
    effects_rules = 0
    taint_rules = 0
    drift_rules = 0
    
    if rule_registry:
        from failcore.core.rules import RuleCategory
        # Count rules by category (factual state from registry)
        dlp_rules = sum(1 for _ in rule_registry.get_rules_by_category(RuleCategory.DLP_API_KEY))
        dlp_rules += sum(1 for _ in rule_registry.get_rules_by_category(RuleCategory.DLP_SECRET))
        dlp_rules += sum(1 for _ in rule_registry.get_rules_by_category(RuleCategory.DLP_PII))
        dlp_rules += sum(1 for _ in rule_registry.get_rules_by_category(RuleCategory.DLP_PAYMENT))
        
        semantic_rules = sum(1 for _ in rule_registry.get_rules_by_category(RuleCategory.SEMANTIC_SECRET_LEAKAGE))
        semantic_rules += sum(1 for _ in rule_registry.get_rules_by_category(RuleCategory.SEMANTIC_INJECTION))
        semantic_rules += sum(1 for _ in rule_registry.get_rules_by_category(RuleCategory.SEMANTIC_DANGEROUS_COMBO))
        semantic_rules += sum(1 for _ in rule_registry.get_rules_by_category(RuleCategory.SEMANTIC_PATH_TRAVERSAL))
    
    # Get mode/config from config (for display only, not for status determination)
    dlp_mode = dlp_config.mode if dlp_config and dlp_status == "enabled" else ""
    semantic_mode = semantic_config.min_severity.value if semantic_config and semantic_status == "enabled" else ""
    effects_mode = f"{effects_config.boundary_preset}{'_enforced' if effects_config and effects_config.enforce_boundary else ''}" if effects_config and effects_status == "enabled" else ""
    taint_mode = taint_config.propagation_mode if taint_config and taint_status == "enabled" else ""
    drift_mode = "analysis_only" if drift_config and drift_config.analysis_only else "enforcement" if drift_status == "enabled" else ""
    
    return RuntimeCapabilities(
        dlp=ModuleCapability(
            status=dlp_status,  # From engine type, not config
            mode=dlp_mode,
            rules_count=dlp_rules if dlp_status == "enabled" else 0,
            config={"redact": dlp_config.redact, "max_scan_chars": dlp_config.max_scan_chars} if dlp_config and dlp_status == "enabled" else {},
        ),
        semantic=ModuleCapability(
            status=semantic_status,  # From engine type, not config
            mode=semantic_mode,
            rules_count=semantic_rules if semantic_status == "enabled" else 0,
            config={"min_severity": semantic_config.min_severity.value} if semantic_config and semantic_status == "enabled" else {},
        ),
        effects=ModuleCapability(
            status=effects_status,  # From engine type, not config
            mode=effects_mode,
            rules_count=effects_rules if effects_status == "enabled" else 0,
            config={"boundary_preset": effects_config.boundary_preset, "enforce_boundary": effects_config.enforce_boundary} if effects_config and effects_status == "enabled" else {},
        ),
        taint=ModuleCapability(
            status=taint_status,  # From engine type, not config
            mode=taint_mode,
            rules_count=taint_rules if taint_status == "enabled" else 0,
            config={"propagation_mode": taint_config.propagation_mode} if taint_config and taint_status == "enabled" else {},
        ),
        drift=ModuleCapability(
            status=drift_status,  # From engine type, not config
            mode=drift_mode,
            rules_count=drift_rules if drift_status == "enabled" else 0,
            config={
                "analysis_only": drift_config.analysis_only,
                "magnitude_threshold_medium": drift_config.magnitude_threshold_medium,
                "magnitude_threshold_high": drift_config.magnitude_threshold_high,
            } if drift_config and drift_status == "enabled" else {},
        ),
    )


__all__ = [
    "ModuleCapability",
    "RuntimeCapabilities",
    "build_capabilities",
]
