# failcore/core/cost/registry.py
"""
Provider Registry - Centralized provider metadata management

Features:
- Register providers with metadata
- Lookup by provider name or alias
- Multi-version support (openai_v1, openai_v2)
- Hot-reload support (future)
- Observable (get_all_providers for debugging)

Usage:
    # Register
    registry.register(openai_v1_metadata)
    registry.register(anthropic_latest_metadata)
    
    # Lookup
    metadata = registry.get("openai", version="v1")
    metadata = registry.get("claude")  # finds by alias
    
    # List all
    all_providers = registry.get_all_providers()
"""

from typing import Dict, List, Optional
from .metadata import ProviderMetadata
import threading


class ProviderRegistry:
    """
    Thread-safe provider metadata registry
    
    Design:
    - Single source of truth for all provider metadata
    - Fast lookup by provider name or alias
    - Multi-version support
    - Thread-safe for concurrent access
    """
    
    def __init__(self):
        """Initialize empty registry"""
        self._providers: Dict[str, ProviderMetadata] = {}
        self._lock = threading.RLock()
    
    def register(self, metadata: ProviderMetadata) -> None:
        """
        Register provider metadata
        
        Args:
            metadata: Provider metadata to register
        
        Examples:
            >>> registry.register(ProviderMetadata(
            ...     provider="openai",
            ...     version="v1",
            ...     extraction_rule=openai_v1_rule,
            ... ))
        """
        with self._lock:
            key = metadata.full_name
            self._providers[key] = metadata
    
    def get(
        self,
        provider: str,
        version: Optional[str] = None,
    ) -> Optional[ProviderMetadata]:
        """
        Get provider metadata by name/alias and optional version
        
        Args:
            provider: Provider name or alias
            version: Optional version (None = latest/any)
        
        Returns:
            ProviderMetadata if found, None otherwise
        
        Lookup Priority:
        1. Exact match: provider_version
        2. Provider match with version
        3. Provider match (any version)
        4. Alias match
        
        Examples:
            >>> registry.get("openai", "v1")  # Returns openai_v1
            >>> registry.get("openai")        # Returns any openai version
            >>> registry.get("claude")        # Returns anthropic (alias match)
        """
        with self._lock:
            # Try exact match first
            if version:
                key = f"{provider}_{version}"
                if key in self._providers:
                    return self._providers[key]
            
            # Try matching by provider name and version
            for metadata in self._providers.values():
                if metadata.matches(provider, version):
                    return metadata
            
            return None
    
    def get_all_providers(self) -> List[ProviderMetadata]:
        """
        Get all registered providers
        
        Returns:
            List of all provider metadata
        
        Useful for:
        - Debugging
        - CLI commands (list-providers)
        - Runtime observability
        """
        with self._lock:
            return list(self._providers.values())
    
    def has_provider(self, provider: str, version: Optional[str] = None) -> bool:
        """
        Check if provider is registered
        
        Args:
            provider: Provider name
            version: Optional version
        
        Returns:
            True if registered
        """
        return self.get(provider, version) is not None
    
    def unregister(self, provider: str, version: str) -> bool:
        """
        Unregister a provider
        
        Args:
            provider: Provider name
            version: Version
        
        Returns:
            True if unregistered, False if not found
        
        Note:
            Mainly for testing. In production, prefer hot-reload.
        """
        with self._lock:
            key = f"{provider}_{version}"
            if key in self._providers:
                del self._providers[key]
                return True
            return False
    
    def clear(self) -> None:
        """
        Clear all registrations
        
        Note:
            Mainly for testing. Use with caution.
        """
        with self._lock:
            self._providers.clear()


# Global registry instance
_default_registry: Optional[ProviderRegistry] = None
_registry_lock = threading.Lock()


def get_default_registry() -> ProviderRegistry:
    """
    Get global default registry (singleton)
    
    Returns:
        Global ProviderRegistry instance
    
    Note:
        Lazy initialization for import-time safety
    """
    global _default_registry
    if _default_registry is None:
        with _registry_lock:
            if _default_registry is None:
                _default_registry = ProviderRegistry()
    return _default_registry


__all__ = [
    "ProviderRegistry",
    "get_default_registry",
]
