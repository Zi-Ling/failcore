# failcore/core/runtime/builder.py
"""
Runtime Builder

Assembles runtime services from configuration.
config.enabled determines Real/NoOp engine selection (startup only).

Design principles:
1. config.enabled only appears in builder (startup)
2. Runtime never sees config or enabled flags
3. Builder returns RuntimeServices (capability bundle)
4. All engines implement same interface (Real/NoOp)
"""

from __future__ import annotations

from typing import Optional
from dataclasses import dataclass

from failcore.config import FailCoreConfig
from failcore.core.runtime.capability import RuntimeCapabilities, build_capabilities
from failcore.core.rules import RuleRegistry, RuleEngine
from failcore.infra.rulesets import FileSystemLoader
from failcore.core.rules.loader import CompositeLoader
from pathlib import Path

# Engine imports
from failcore.core.guards.dlp.engine import RealDlpEngine, NoOpDlpEngine, DlpEngine
from failcore.core.guards.semantic.engine import RealSemanticEngine, NoOpSemanticEngine, SemanticEngine
from failcore.core.guards.effects.engine import RealEffectsEngine, NoOpEffectsEngine, EffectsEngine
from failcore.core.guards.taint.engine import RealTaintEngine, NoOpTaintEngine, TaintEngine
from failcore.core.replay.drift.engine import RealDriftEngine, NoOpDriftEngine, DriftEngine


@dataclass(frozen=True)
class RuntimeServices:
    """
    Runtime services bundle
    
    Contains all engines and capabilities.
    Runtime code uses these services directly (no config checks).
    """
    
    # Engines (always present, Real or NoOp)
    dlp: DlpEngine
    semantic: SemanticEngine
    effects: EffectsEngine
    taint: TaintEngine
    drift: DriftEngine
    
    # Capabilities (read-only, for observability)
    capabilities: RuntimeCapabilities
    
    # Optional: Rule registry (if needed by runtime)
    rule_registry: Optional[RuleRegistry] = None


def build_runtime_services(config: FailCoreConfig) -> RuntimeServices:
    """
    Build runtime services from configuration.
    
    This is the ONLY place where config.enabled is checked.
    After this, runtime only sees engine instances.
    
    Args:
        config: FailCore configuration
    
    Returns:
        RuntimeServices with all engines (Real or NoOp)
    """
    # Create rule registry and loader
    default_path = Path(__file__).parent.parent.parent / "config" / "rulesets" / "default"
    loader = CompositeLoader([
        FileSystemLoader(Path.home() / ".failcore" / "rulesets"),
        FileSystemLoader(default_path),
    ])
    rule_registry = RuleRegistry(loader)
    
    # Build engines based on config.enabled (STARTUP ONLY)
    
    # DLP Engine
    if config.dlp.enabled:
        rule_registry.load_ruleset("dlp")
        from failcore.core.rules import RuleAction
        rule_engine = RuleEngine(rule_registry, default_action=RuleAction.ALLOW)
        dlp_engine: DlpEngine = RealDlpEngine(
            rule_registry=rule_registry,
            rule_engine=rule_engine,
            mode=config.dlp.mode,
            redact=config.dlp.redact,
            max_scan_chars=config.dlp.max_scan_chars,
        )
    else:
        dlp_engine = NoOpDlpEngine()
    
    # Semantic Engine
    if config.semantic.enabled:
        rule_registry.load_ruleset("semantic")
        from failcore.core.rules import RuleAction
        rule_engine = RuleEngine(rule_registry, default_action=RuleAction.ALLOW)
        semantic_engine: SemanticEngine = RealSemanticEngine(
            rule_registry=rule_registry,
            rule_engine=rule_engine,
            min_severity=config.semantic.min_severity,
            enabled_categories=config.semantic.enabled_categories,
        )
    else:
        semantic_engine = NoOpSemanticEngine()
    
    # Effects Engine
    if config.effects.enabled:
        from failcore.config.boundaries import get_boundary
        boundary = get_boundary(config.effects.boundary_preset)
        effects_engine: EffectsEngine = RealEffectsEngine(boundary=boundary)
    else:
        effects_engine = NoOpEffectsEngine()
    
    # Taint Engine
    if config.taint.enabled:
        taint_engine: TaintEngine = RealTaintEngine(
            propagation_mode=config.taint.propagation_mode,
            max_path_depth=config.taint.max_path_depth,
            max_paths_per_step=config.taint.max_paths_per_step,
        )
    else:
        taint_engine = NoOpTaintEngine()
    
    # Drift Engine
    if config.drift.enabled:
        drift_engine: DriftEngine = RealDriftEngine(
            magnitude_threshold_medium=config.drift.magnitude_threshold_medium,
            magnitude_threshold_high=config.drift.magnitude_threshold_high,
            ignore_fields=config.drift.ignore_fields,
            analysis_only=config.drift.analysis_only,
        )
    else:
        drift_engine = NoOpDriftEngine()
    
    # Build capabilities (from engines/registry factual state, not config.enabled)
    capabilities = build_capabilities(
        dlp_engine=dlp_engine,
        semantic_engine=semantic_engine,
        effects_engine=effects_engine,
        taint_engine=taint_engine,
        drift_engine=drift_engine,
        dlp_config=config.dlp,
        semantic_config=config.semantic,
        effects_config=config.effects,
        taint_config=config.taint,
        drift_config=config.drift,
        rule_registry=rule_registry,
    )
    
    return RuntimeServices(
        dlp=dlp_engine,
        semantic=semantic_engine,
        effects=effects_engine,
        taint=taint_engine,
        drift=drift_engine,
        capabilities=capabilities,
        rule_registry=rule_registry,
    )


__all__ = [
    "RuntimeServices",
    "build_runtime_services",
]
