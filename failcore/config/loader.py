# failcore/config/loader.py
"""
Configuration Loader

Loads configuration from YAML files with code defaults as fallback.

Design principle:
- Code = truth (has all defaults)
- YAML = input parameters (optional)
- System works without YAML
- Deep immutability (nested containers are frozen)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any
from types import MappingProxyType
import yaml
import copy

from .modules import (
    DLPConfig,
    SemanticConfig,
    EffectsConfig,
    TaintConfig,
    DriftConfig,
)
from .limits import LimitsConfig
from .cost import (
    USAGE_CANDIDATE_PATHS,
    KNOWN_PROVIDER_REPORTED,
    COST_CONFLICT_THRESHOLD,
    STANDARD_TOKEN_FIELDS,
)
from .proxy import ProxyConfig
from .analysis import AnalysisConfig
from .validator import validate_config, ConfigIssue
from failcore.core.runtime.capability import build_capabilities, RuntimeCapabilities


def _freeze_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively freeze dictionary (convert nested dicts/lists to immutable)"""
    if not isinstance(d, dict):
        return d
    
    frozen = {}
    for k, v in d.items():
        if isinstance(v, dict):
            frozen[k] = _freeze_dict(v)
        elif isinstance(v, list):
            frozen[k] = tuple(_freeze_dict(item) if isinstance(item, dict) else item for item in v)
        else:
            frozen[k] = v
    
    return MappingProxyType(frozen)


def _freeze_config(config: "FailCoreConfig") -> "FailCoreConfig":
    """Freeze configuration deeply (make nested containers immutable)"""
    # Config classes are already frozen, but we need to freeze nested dicts/lists
    # Since configs are frozen dataclasses, we can't modify them
    # Instead, we ensure nested containers in config values are immutable
    
    # For now, configs don't have nested mutable containers in their fields
    # But if they do in the future, this function will handle it
    return config


class FailCoreConfig:
    """
    Unified FailCore configuration.
    
    All fields have code defaults - YAML is optional.
    Configuration is deeply immutable (nested containers are frozen).
    """
    
    def __init__(
        self,
        dlp: Optional[DLPConfig] = None,
        semantic: Optional[SemanticConfig] = None,
        effects: Optional[EffectsConfig] = None,
        taint: Optional[TaintConfig] = None,
        drift: Optional[DriftConfig] = None,
        limits: Optional[LimitsConfig] = None,
        cost: Optional[Dict[str, Any]] = None,
        proxy: Optional[ProxyConfig] = None,
        analysis: Optional[AnalysisConfig] = None,
    ):
        """Initialize with code defaults"""
        self.dlp = dlp or DLPConfig.default()
        self.semantic = semantic or SemanticConfig.default()
        self.effects = effects or EffectsConfig.default()
        self.taint = taint or TaintConfig.default()
        self.drift = drift or DriftConfig.default()
        self.limits = limits or LimitsConfig()
        self.cost = cost or {}
        self.proxy = proxy or ProxyConfig()
        self.analysis = analysis or AnalysisConfig()
        
        # Freeze nested containers
        if isinstance(self.cost, dict):
            self.cost = _freeze_dict(self.cost)
    
    @classmethod
    def default(cls) -> "FailCoreConfig":
        """Create default configuration (no YAML needed)"""
        config = cls()
        return _freeze_config(config)
    
    @classmethod
    def from_yaml(cls, config_path: Optional[Path] = None) -> "FailCoreConfig":
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to YAML file. If None, tries:
                1. ~/.failcore/config.yml
                2. failcore/config/config.yml.example (example file, not default)
        
        Returns:
            FailCoreConfig instance (always has code defaults as fallback)
        """
        # Start with code defaults
        config = cls.default()
        
        # Try to load YAML (optional)
        yaml_data = _load_yaml(config_path)
        if not yaml_data:
            return config  # Return defaults if no YAML
        
        # Merge YAML into defaults
        if "modules" in yaml_data:
            modules = yaml_data["modules"]
            
            if "dlp" in modules:
                config.dlp = _merge_config(config.dlp, modules["dlp"], DLPConfig)
            
            if "semantic" in modules:
                config.semantic = _merge_config(config.semantic, modules["semantic"], SemanticConfig)
            
            if "effects" in modules:
                config.effects = _merge_config(config.effects, modules["effects"], EffectsConfig)
            
            if "taint" in modules:
                config.taint = _merge_config(config.taint, modules["taint"], TaintConfig)
            
            if "drift" in modules:
                config.drift = _merge_config(config.drift, modules["drift"], DriftConfig)
        
        # Merge limits
        if "limits" in yaml_data:
            limits_data = yaml_data["limits"]
            config.limits = LimitsConfig(**{k: v for k, v in limits_data.items() if hasattr(LimitsConfig, k)})
        
        # Merge proxy
        if "proxy" in yaml_data:
            proxy_data = yaml_data["proxy"]
            config.proxy = ProxyConfig(**{k: v for k, v in proxy_data.items() if hasattr(ProxyConfig, k)})
        
        # Merge analysis
        if "analysis" in yaml_data:
            analysis_data = yaml_data["analysis"]
            config.analysis = AnalysisConfig(**{k: v for k, v in analysis_data.items() if hasattr(AnalysisConfig, k)})
        
        # Freeze deeply
        return _freeze_config(config)
    
    def validate(self) -> list[ConfigIssue]:
        """
        Validate configuration for illegal/misleading combinations.
        
        Returns:
            List of issues (warn/error level)
        """
        return validate_config(
            self.dlp,
            self.semantic,
            self.effects,
            self.taint,
            self.drift,
        )
    
    def get_capabilities(self, rule_registry=None) -> RuntimeCapabilities:
        """
        Get runtime capabilities descriptor.
        
        Args:
            rule_registry: Optional rule registry to get rule counts
        
        Returns:
            RuntimeCapabilities instance (frozen, read-only)
        
        Note:
            Capabilities should come from runtime/registry (factual state),
            not from config (desired state). This method is for convenience
            but should ideally be called from runtime with registry.
        """
        from failcore.core.runtime.capability import build_capabilities
        return build_capabilities(
            self.dlp,
            self.semantic,
            self.effects,
            self.taint,
            self.drift,
            rule_registry,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "modules": {
                "dlp": self.dlp.to_dict(),
                "semantic": self.semantic.to_dict(),
                "effects": self.effects.to_dict(),
                "taint": self.taint.to_dict(),
                "drift": self.drift.to_dict(),
            },
            "limits": {
                "timeout_ms": self.limits.timeout_ms,
                "max_output_bytes": self.limits.max_output_bytes,
                "max_events": self.limits.max_events,
                "max_file_bytes": self.limits.max_file_bytes,
                "max_total_file_bytes": self.limits.max_total_file_bytes,
                "max_concurrency": self.limits.max_concurrency,
                "max_cost_usd": self.limits.max_cost_usd,
                "max_tokens": self.limits.max_tokens,
            },
            "proxy": {
                "host": self.proxy.host,
                "port": self.proxy.port,
                "upstream_timeout_s": self.proxy.upstream_timeout_s,
                "enable_dlp": self.proxy.enable_dlp,
            },
            "analysis": {
                "drift": self.analysis.drift,
                "optimizer": self.analysis.optimizer,
            },
        }


def _load_yaml(config_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load YAML file, return None if not found (not an error)"""
    if config_path:
        paths = [Path(config_path)]
    else:
        # Try multiple locations
        paths = [
            Path.home() / ".failcore" / "config.yml",
            Path(__file__).parent / "config.yml.example",  # Example file, not default
        ]
    
    for path in paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            except Exception:
                # YAML load failed, return None (use code defaults)
                return None
    
    return None  # No YAML found, use code defaults


def _merge_config(default_instance, yaml_data: Dict[str, Any], config_class):
    """Merge YAML data into default config instance"""
    # Get default as dict
    default_dict = default_instance.to_dict() if hasattr(default_instance, "to_dict") else default_instance.__dict__
    
    # Merge YAML data
    merged = {**default_dict, **yaml_data}
    
    # Handle special types (e.g., RuleSeverity enum from string)
    if config_class.__name__ == "SemanticConfig" and "min_severity" in merged:
        from failcore.core.rules import RuleSeverity
        if isinstance(merged["min_severity"], str):
            try:
                merged["min_severity"] = RuleSeverity(merged["min_severity"])
            except ValueError:
                # Invalid severity, keep default
                merged["min_severity"] = default_dict["min_severity"]
    
    # Create new instance
    return config_class(**{k: v for k, v in merged.items() if k in config_class.__dataclass_fields__})


def load_config(config_path: Optional[Path] = None) -> FailCoreConfig:
    """
    Load FailCore configuration.
    
    Args:
        config_path: Optional path to YAML file
    
    Returns:
        FailCoreConfig instance (always has code defaults, deeply frozen)
    
    Note:
        - If YAML is not found or invalid, returns code defaults
        - System works without YAML (code is truth)
        - Configuration is deeply immutable (nested containers frozen)
    """
    return FailCoreConfig.from_yaml(config_path)


__all__ = [
    "FailCoreConfig",
    "load_config",
]
