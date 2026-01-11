# failcore/core/validate/validator.py
"""
Unified validator interface.

This module defines the core interface that all builtin must implement.
All builtin return DecisionV1 objects, making the system uniform and composable.

Design principles:
- Every validator implements the same interface
- All builtin return List[DecisionV1]
- Configuration is explicit and typed
- Validators are stateless (policy + context -> decisions)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .contracts import (
    Context,
    Decision,
    Policy,
    ValidatorConfig,
)


class BaseValidator(ABC):
    """
    Base validator interface.
    
    All builtin must implement this interface to ensure uniformity.
    
    Key methods:
    - id: Unique validator identifier
    - domain: Validator domain/pack (e.g., 'security', 'network')
    - config_schema: JSON schema for validator configuration
    - evaluate: Execute validation and return decisions
    """
    
    @property
    @abstractmethod
    def id(self) -> str:
        """
        Unique validator identifier.
        
        Convention: Use lowercase with underscores (e.g., 'network_ssrf')
        """
        pass
    
    @property
    @abstractmethod
    def domain(self) -> str:
        """
        Validator domain/pack.
        
        Standard domains: 'contract', 'type', 'security', 'network', 'resource'
        Custom domains are allowed for extensions.
        """
        pass
    
    @property
    def config_schema(self) -> Optional[Dict[str, Any]]:
        """
        JSON schema for validator configuration.
        
        Returns None if validator doesn't require configuration.
        
        Example:
        {
            "type": "object",
            "properties": {
                "allowlist": {"type": "array", "items": {"type": "string"}},
                "block_internal": {"type": "boolean"}
            }
        }
        """
        return None
    
    @property
    def default_config(self) -> Dict[str, Any]:
        """
        Default configuration for this validator.
        
        Used when no explicit configuration is provided.
        """
        return {}
    
    @abstractmethod
    def evaluate(
        self,
        context: Context,
        config: Optional[ValidatorConfig] = None
    ) -> List[Decision]:
        """
        Execute validation and return decisions.
        
        Args:
            context: Validation context (tool, params, result, etc.)
            config: Validator configuration (from policy)
        
        Returns:
            List of validation decisions (empty list = no violations)
        
        Notes:
        - Return empty list if validation passes
        - Return one or more DecisionV1 objects if violations are found
        - Decisions can be ALLOW, WARN, or BLOCK
        - Each decision must have a stable code (e.g., FC_NET_SSRF_INTERNAL)
        """
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id!r}, domain={self.domain!r})"


__all__ = [
    "BaseValidator",
]
