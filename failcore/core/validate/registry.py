# failcore/core/validate/registry.py
"""
Validator Registry: Central registry for all builtin.

The registry provides:
- Validator registration (register)
- Validator discovery (list_validators, get)
- Domain filtering (get_by_domain)
- Plugin discovery support (for future use)

Design principles:
- Single source of truth for available builtin
- No hard-coded validator imports
- Supports both built-in and plugin builtin
- Thread-safe (uses locks for registration)
"""

from __future__ import annotations

from typing import Dict, List, Optional
import threading

from .validator import BaseValidator


class ValidatorRegistry:
    """
    Central registry for all builtin.
    
    Responsibilities:
    - Store registered builtin
    - Provide validator lookup by ID
    - List all builtin or filter by domain
    - Support plugin discovery
    
    Usage:
    ```python
    # Register a validator
    registry = ValidatorRegistry()
    registry.register(MyValidator())
    
    # Get validator by ID
    validator = registry.get("network_ssrf")
    
    # List all builtin
    all_validators = registry.list_validators()
    
    # List builtin by domain
    security_validators = registry.get_by_domain("security")
    ```
    """
    
    def __init__(self):
        self._validators: Dict[str, BaseValidator] = {}
        self._lock = threading.Lock()
    
    def register(self, validator: BaseValidator) -> None:
        """
        Register a validator.
        
        Args:
            validator: Validator instance to register
        
        Raises:
            ValueError: If validator ID is already registered
        """
        with self._lock:
            if validator.id in self._validators:
                raise ValueError(
                    f"Validator '{validator.id}' is already registered. "
                    f"Existing: {self._validators[validator.id]}, "
                    f"New: {validator}"
                )
            self._validators[validator.id] = validator
    
    def register_multiple(self, validators: List[BaseValidator]) -> None:
        """
        Register multiple builtin.
        
        Args:
            validators: List of validator instances
        """
        for validator in validators:
            self.register(validator)
    
    def unregister(self, validator_id: str) -> None:
        """
        Unregister a validator.
        
        Args:
            validator_id: Validator ID to unregister
        """
        with self._lock:
            if validator_id in self._validators:
                del self._validators[validator_id]
    
    def get(self, validator_id: str) -> Optional[BaseValidator]:
        """
        Get validator by ID.
        
        Args:
            validator_id: Validator ID
        
        Returns:
            Validator instance or None if not found
        """
        return self._validators.get(validator_id)
    
    def has(self, validator_id: str) -> bool:
        """Check if validator is registered"""
        return validator_id in self._validators
    
    def list_validators(self) -> List[BaseValidator]:
        """
        List all registered builtin.
        
        Returns:
            List of all builtin (unordered)
        """
        return list(self._validators.values())
    
    def get_by_domain(self, domain: str) -> List[BaseValidator]:
        """
        Get all builtin in a specific domain.
        
        Args:
            domain: Domain name (e.g., 'security', 'network')
        
        Returns:
            List of builtin in the specified domain
        """
        return [
            v for v in self._validators.values()
            if v.domain == domain
        ]
    
    def list_domains(self) -> List[str]:
        """
        List all registered domains.
        
        Returns:
            Sorted list of unique domain names
        """
        domains = {v.domain for v in self._validators.values()}
        return sorted(domains)
    
    def count(self) -> int:
        """Get count of registered builtin"""
        return len(self._validators)
    
    def clear(self) -> None:
        """Clear all registered builtin (useful for testing)"""
        with self._lock:
            self._validators.clear()
    
    def __repr__(self) -> str:
        return (
            f"ValidatorRegistry("
            f"builtin={len(self._validators)}, "
            f"domains={self.list_domains()})"
        )


# Global registry instance
_global_registry: Optional[ValidatorRegistry] = None
_global_registry_lock = threading.Lock()


def get_global_registry() -> ValidatorRegistry:
    """
    Get the global validator registry.
    
    The global registry is lazily initialized on first access.
    
    Returns:
        Global ValidatorRegistry instance
    """
    global _global_registry
    
    if _global_registry is None:
        with _global_registry_lock:
            if _global_registry is None:
                _global_registry = ValidatorRegistry()
    
    return _global_registry


def set_global_registry(registry: ValidatorRegistry) -> None:
    """
    Set the global validator registry.
    
    This is useful for testing or custom initialization.
    
    Args:
        registry: ValidatorRegistry instance to use as global registry
    """
    global _global_registry
    with _global_registry_lock:
        _global_registry = registry


def reset_global_registry() -> None:
    """
    Reset the global registry.
    
    Useful for testing. Creates a new empty registry.
    """
    global _global_registry
    with _global_registry_lock:
        _global_registry = None


__all__ = [
    "ValidatorRegistry",
    "get_global_registry",
    "set_global_registry",
    "reset_global_registry",
]
