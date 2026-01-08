# failcore/core/cost/metadata.py
"""
Provider Metadata Registry - Configuration-driven cost extraction

Core Architecture:
- ProviderMetadata: Declarative provider configuration
- ExtractionRule: Path finding + field mapping rules
- Pipeline: PathFinder → TypeNormalizer → FieldMapper
- Registry: Centralized provider metadata management

Benefits:
- Zero-downtime evolution (hot-reload configs)
- Multi-version coexistence (openai_v1, openai_v2)
- Community-friendly (YAML/JSON contributions)
- Observable (trace which rule was used)
- AI-friendly (LLM can generate new adapters)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable, Type
from enum import Enum


class FieldType(str, Enum):
    """Field type for validation"""
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    BOOL = "bool"
    ANY = "any"


@dataclass
class FieldMapping:
    """
    Field mapping rule: source field → target field + type conversion
    
    Examples:
        # OpenAI: prompt_tokens → input_tokens
        FieldMapping(source="prompt_tokens", target="input_tokens", type=FieldType.INT)
        
        # Anthropic: already uses input_tokens
        FieldMapping(source="input_tokens", target="input_tokens", type=FieldType.INT)
    """
    source: str              # Source field name in provider response
    target: str              # Target field name in CostUsage
    type: FieldType          # Expected field type
    optional: bool = False   # Whether field is optional
    default: Any = None      # Default value if missing


@dataclass
class ExtractionRule:
    """
    Extraction rule: paths to find usage + field mappings
    
    Examples:
        # OpenAI v1
        ExtractionRule(
            paths=["usage", "choices[0].message.usage"],
            field_mappings=[
                FieldMapping("prompt_tokens", "input_tokens", FieldType.INT),
                FieldMapping("completion_tokens", "output_tokens", FieldType.INT),
            ]
        )
    """
    paths: List[str]                      # Priority-ordered paths to find usage
    field_mappings: List[FieldMapping]    # Field name mappings
    requires_all: List[str] = field(default_factory=list)  # Required fields (validation)
    
    def __post_init__(self):
        """Validate rule configuration"""
        if not self.paths:
            raise ValueError("ExtractionRule must have at least one path")
        if not self.field_mappings:
            raise ValueError("ExtractionRule must have at least one field mapping")


@dataclass
class ProviderMetadata:
    """
    Provider metadata: comprehensive configuration for a provider
    
    Supports:
    - Multi-version (openai_v1, openai_v2)
    - Custom extraction rules
    - Optional schema validation
    - Source tracking (estimated vs reported)
    
    Examples:
        # OpenAI v1
        ProviderMetadata(
            provider="openai",
            version="v1",
            extraction_rule=ExtractionRule(...),
            estimated=False,  # Provider-reported
        )
        
        # Generic fallback
        ProviderMetadata(
            provider="generic",
            version="latest",
            extraction_rule=ExtractionRule(...),
            estimated=True,   # Estimated
        )
    """
    provider: str                          # Provider name (e.g., "openai", "anthropic")
    version: str                           # Version (e.g., "v1", "v2", "latest")
    extraction_rule: ExtractionRule        # Extraction rule
    estimated: bool = False                # Whether cost is estimated (vs provider-reported)
    validator: Optional[Type[Any]] = None  # Optional Pydantic model for validation
    aliases: List[str] = field(default_factory=list)  # Alternative names
    
    @property
    def full_name(self) -> str:
        """Full provider name: provider_version"""
        return f"{self.provider}_{self.version}"
    
    def matches(self, provider: Optional[str], version: Optional[str] = None) -> bool:
        """
        Check if this metadata matches given provider/version
        
        Args:
            provider: Provider name or alias
            version: Version (None matches any version)
        
        Returns:
            True if matches
        """
        if not provider:
            return False
        
        # Check provider name
        provider_match = (
            provider.lower() == self.provider.lower() or
            provider.lower() in [alias.lower() for alias in self.aliases]
        )
        
        if not provider_match:
            return False
        
        # If version specified, check version match
        if version:
            return version.lower() == self.version.lower()
        
        return True


__all__ = [
    "FieldType",
    "FieldMapping",
    "ExtractionRule",
    "ProviderMetadata",
]
