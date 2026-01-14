# failcore/core/validate/constants.py
"""
Validation constants: Metadata keys and system identifiers.

This module defines constants for system-level metadata keys to avoid
magic strings and prevent typos that would silently fail.

All system metadata keys use the "failcore.sys.*" namespace to avoid
conflicts with user-defined metadata.
"""

from typing import Final


class MetaKeys:
    """
    System metadata keys for validation context.
    
    These keys are used in Context.metadata to pass system-level information
    (timestamp, override tokens, etc.) without polluting user metadata.
    
    All keys use the "failcore.sys.*" namespace prefix.
    """
    
    # Time-related
    TIMESTAMP: Final[str] = "failcore.sys.timestamp"
    """Current timestamp (ISO8601 format with timezone) for validation decisions."""
    
    # Override-related
    OVERRIDE_TOKEN: Final[str] = "failcore.sys.override_token"
    """Emergency override token for breakglass mode."""
    
    # Trace-related
    TRACE_ID: Final[str] = "failcore.sys.trace_id"
    """Trace identifier for audit correlation."""
    
    RUN_ID: Final[str] = "failcore.sys.run_id"
    """Run identifier for audit correlation."""
    
    # Source-related
    TRACE_SOURCE: Final[str] = "failcore.sys.trace_source"
    """Trace source type (path/events) for drift validation."""
    
    TRACE_COMPLETENESS: Final[str] = "failcore.sys.trace_completeness"
    """Trace completeness indicator for drift validation."""
    
    # Sandbox-related
    SANDBOX_ROOT: Final[str] = "failcore.sys.sandbox_root"
    """Sandbox root directory for path validation."""
    
    @classmethod
    def is_system_key(cls, key: str) -> bool:
        """
        Check if a metadata key is a system key.
        
        Args:
            key: Metadata key to check
        
        Returns:
            True if key is a system key (starts with "failcore.sys.")
        """
        return key.startswith("failcore.sys.")


__all__ = ["MetaKeys"]
