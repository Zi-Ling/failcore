# failcore/core/resources.py
"""
SessionResources - unified resource container for a FailCore session

This module enforces resource ownership: all execution resources (registry, recorder, 
sandbox, janitor) must be created and owned by a Session, not independently.

Design:
- SessionResources is the ONLY way to pass resources to Executor
- Prevents accidental resource leaks by centralizing lifecycle management
- Makes resource dependencies explicit in type signatures
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any
import secrets


@dataclass
class SessionResources:
    """
    Container for all session-owned resources.
    
    This class is the contract between Session and Executor:
    - Session creates and owns all resources
    - Executor receives resources via this container
    - No Executor should create its own resources
    
    Fields:
        session_id: Unique session identifier
        sandbox_root: Root directory for file operations
        process_registry: Registry of owned PIDs/process groups
        trace_recorder: Trace event recorder
        janitor: Resource cleanup manager
        _creation_token: Private token to prevent unauthorized creation
    """
    
    session_id: str
    sandbox_root: Path
    process_registry: Any  # ProcessRegistry (avoid circular import)
    trace_recorder: Any    # TraceRecorder (avoid circular import)
    janitor: Any           # ResourceJanitor (avoid circular import)
    
    # Private token to enforce creation through Session only
    # If you try to create SessionResources manually, you'll get wrong token
    _creation_token: str = ""
    
    def __post_init__(self):
        """Validate creation token"""
        if not self._creation_token:
            raise RuntimeError(
                "SessionResources must be created through Session.create_resources(), "
                "not directly. This ensures proper resource lifecycle management."
            )
        
        # Validate token matches expected pattern
        if not _verify_creation_token(self._creation_token):
            raise RuntimeError(
                "Invalid SessionResources creation token. "
                "Resources must be created through authorized Session factory."
            )
    
    @classmethod
    def create(
        cls,
        session_id: str,
        sandbox_root: Path,
        process_registry: Any,
        trace_recorder: Any,
        janitor: Any,
    ) -> SessionResources:
        """
        Factory method for creating SessionResources (internal use only).
        
        This should ONLY be called by Session or authorized factory functions.
        The creation token mechanism enforces this constraint.
        
        Args:
            session_id: Unique session identifier
            sandbox_root: Sandbox root directory
            process_registry: ProcessRegistry instance
            trace_recorder: TraceRecorder instance
            janitor: ResourceJanitor instance
            
        Returns:
            SessionResources instance with valid creation token
        """
        # Generate creation token
        token = _generate_creation_token()
        
        return cls(
            session_id=session_id,
            sandbox_root=sandbox_root,
            process_registry=process_registry,
            trace_recorder=trace_recorder,
            janitor=janitor,
            _creation_token=token,
        )
    
    def validate_token(self) -> bool:
        """Validate that this instance has a valid creation token"""
        return _verify_creation_token(self._creation_token)


# Token management (private implementation)
_TOKEN_PREFIX = "failcore_session_"
_TOKEN_LENGTH = 32


def _generate_creation_token() -> str:
    """Generate a valid creation token"""
    return _TOKEN_PREFIX + secrets.token_hex(_TOKEN_LENGTH // 2)


def _verify_creation_token(token: str) -> bool:
    """Verify a creation token is valid"""
    if not token:
        return False
    if not token.startswith(_TOKEN_PREFIX):
        return False
    if len(token) != len(_TOKEN_PREFIX) + _TOKEN_LENGTH:
        return False
    return True


__all__ = ["SessionResources"]
