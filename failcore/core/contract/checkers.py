# failcore/core/contract/checkers.py
"""
Contract checkers - Semantic validation rules
"""

import json
from typing import Any, Optional, Dict
from .types import ExpectedKind, DriftType, Decision
from .model import ContractResult


class ContractChecker:
    """
    Contract validation checker
    
    Provides semantic validation of tool outputs against expected contracts.
    """
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize checker
        
        Args:
            strict_mode: If True, drift causes BLOCK instead of WARN
        """
        self.strict_mode = strict_mode
    
    def check_output(
        self,
        value: Any,
        expected_kind: Optional[ExpectedKind] = None,
        schema: Optional[Dict[str, Any]] = None,
    ) -> ContractResult:
        """
        Check output value against contract
        
        Args:
            value: The actual output value
            expected_kind: Expected output kind (if specified)
            schema: Optional schema for validation
            
        Returns:
            ContractResult with decision and details
        """
        # If no expected kind specified, accept anything
        if expected_kind is None:
            return ContractResult(decision=Decision.OK)
        
        # Determine observed kind
        observed_kind = self._infer_kind(value)
        
        # Check kind mismatch
        if expected_kind.value != observed_kind:
            return self._handle_kind_mismatch(
                expected_kind=expected_kind,
                observed_kind=observed_kind,
                value=value,
            )
        
        # If kinds match, check deeper constraints
        if expected_kind == ExpectedKind.JSON:
            return self._check_json_contract(value, schema)
        
        return ContractResult(decision=Decision.OK)
    
    def _infer_kind(self, value: Any) -> str:
        """
        Infer the kind of output value
        
        Args:
            value: The output value
            
        Returns:
            Kind string (json, text, binary, null)
        """
        if value is None:
            return "null"
        
        if isinstance(value, (dict, list)):
            return "json"
        
        if isinstance(value, str):
            # Try to parse as JSON
            try:
                json.loads(value)
                return "json"
            except (json.JSONDecodeError, TypeError):
                return "text"
        
        if isinstance(value, bytes):
            return "binary"
        
        # Numbers, booleans, etc. are treated as JSON-compatible
        return "json"
    
    def _handle_kind_mismatch(
        self,
        expected_kind: ExpectedKind,
        observed_kind: str,
        value: Any,
    ) -> ContractResult:
        """Handle output kind mismatch"""
        
        # Generate helpful reason message
        reason = f"Output is {observed_kind}, not valid {expected_kind.value.upper()}"
        
        # Get excerpt for diagnostics
        excerpt = self._get_excerpt(value)
        
        # Decide: WARN or BLOCK based on strict mode
        decision = Decision.BLOCK if self.strict_mode else Decision.WARN
        
        return ContractResult(
            decision=decision,
            drift_type=DriftType.OUTPUT_KIND_MISMATCH,
            expected_kind=expected_kind,
            observed_kind=observed_kind,
            reason=reason,
            raw_excerpt=excerpt,
        )
    
    def _check_json_contract(
        self,
        value: Any,
        schema: Optional[Dict[str, Any]],
    ) -> ContractResult:
        """
        Check JSON-specific contract constraints
        
        Args:
            value: JSON value (dict, list, or JSON string)
            schema: Optional schema definition
            
        Returns:
            ContractResult
        """
        # If value is string, try to parse
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as e:
                decision = Decision.BLOCK if self.strict_mode else Decision.WARN
                return ContractResult(
                    decision=decision,
                    drift_type=DriftType.INVALID_JSON,
                    expected_kind=ExpectedKind.JSON,
                    observed_kind="text",
                    reason=f"Invalid JSON: {str(e)}",
                    parse_error=str(e),
                    raw_excerpt=self._get_excerpt(value),
                )
            value = parsed
        
        # If no schema provided, JSON is valid
        if schema is None:
            return ContractResult(decision=Decision.OK)
        
        # Check schema constraints
        return self._validate_schema(value, schema)
    
    def _validate_schema(
        self,
        value: Any,
        schema: Dict[str, Any],
    ) -> ContractResult:
        """
        Validate value against schema
        
        Simple schema validation supporting:
        - required: list of required field names
        - properties: field definitions (future expansion)
        
        Args:
            value: Parsed JSON value
            schema: Schema definition
            
        Returns:
            ContractResult
        """
        # Check required fields
        required = schema.get("required", [])
        if required and isinstance(value, dict):
            missing = [field for field in required if field not in value]
            if missing:
                decision = Decision.BLOCK if self.strict_mode else Decision.WARN
                return ContractResult(
                    decision=decision,
                    drift_type=DriftType.MISSING_REQUIRED_FIELDS,
                    expected_kind=ExpectedKind.JSON,
                    observed_kind="json",
                    reason=f"Missing required fields: {', '.join(missing)}",
                    fields_missing=missing,
                )
        
        # Future: Add more schema validation (types, patterns, etc.)
        
        return ContractResult(decision=Decision.OK)
    
    def _get_excerpt(self, value: Any, max_length: int = 100) -> str:
        """Get a short excerpt of the value for diagnostics"""
        text = str(value)
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."


# Convenience function
def check_output(
    value: Any,
    expected_kind: Optional[ExpectedKind] = None,
    schema: Optional[Dict[str, Any]] = None,
    strict_mode: bool = False,
) -> ContractResult:
    """
    Check output value against contract
    
    Convenience function that creates a checker and validates.
    
    Args:
        value: The actual output value
        expected_kind: Expected output kind
        schema: Optional schema for validation
        strict_mode: If True, drift causes BLOCK instead of WARN
        
    Returns:
        ContractResult with decision and details
    """
    checker = ContractChecker(strict_mode=strict_mode)
    return checker.check_output(value, expected_kind, schema)

