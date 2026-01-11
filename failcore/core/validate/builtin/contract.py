# failcore/core/validate/builtin/contract.py
"""
Contract-based builtin for output validation

Bridges contract/ layer with validate/ layer.
"""

from typing import Any, Dict, Optional, Callable, Literal
from dataclasses import dataclass, field
from failcore.core.contract import ExpectedKind, check_output, ContractResult


# Internal types for builtin validators
@dataclass
class ValidationResult:
    """Validation result for builtin validators"""
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    severity: Literal["ok", "warn", "block"] = "ok"
    validator: Optional[str] = None
    code: Optional[str] = None
    
    @property
    def valid(self) -> bool:
        return self.severity != "block"
    
    @classmethod
    def success(cls, message: str = "", **kwargs) -> "ValidationResult":
        return cls(message=message, severity="ok", **kwargs)
    
    @classmethod
    def warning(cls, message: str, details: Optional[Dict[str, Any]] = None, code: Optional[str] = None, **kwargs) -> "ValidationResult":
        return cls(message=message, severity="warn", details=details or {}, code=code, **kwargs)
    
    @classmethod
    def failure(cls, message: str, details: Optional[Dict[str, Any]] = None, code: Optional[str] = None, **kwargs) -> "ValidationResult":
        return cls(message=message, severity="block", details=details or {}, code=code, **kwargs)


@dataclass
class PreconditionValidator:
    """Precondition validator for builtin"""
    name: str
    condition: Callable[[Dict[str, Any]], ValidationResult]
    message: str = ""
    code: Optional[str] = None
    
    def validate(self, context: Dict[str, Any]) -> ValidationResult:
        try:
            return self.condition(context)
        except Exception as e:
            return ValidationResult.failure(
                f"Precondition '{self.name}' check failed: {e}",
                {"condition": self.name, "error": str(e)},
                code=self.code or "PRECONDITION_ERROR",
                validator=self.name,
            )


@dataclass
class PostconditionValidator:
    """Postcondition validator for builtin"""
    name: str
    condition: Callable[[Dict[str, Any]], ValidationResult]
    message: str = ""
    code: Optional[str] = None
    
    def validate(self, context: Dict[str, Any]) -> ValidationResult:
        try:
            return self.condition(context)
        except Exception as e:
            return ValidationResult.failure(
                f"Postcondition '{self.name}' check failed: {e}",
                {"condition": self.name, "error": str(e)},
                code=self.code or "POSTCONDITION_ERROR",
                validator=self.name,
            )


def output_contract_postcondition(
    expected_kind: Optional[ExpectedKind] = None,
    schema: Optional[Dict[str, Any]] = None,
    strict_mode: bool = False,
) -> PostconditionValidator:
    """
    Create a postcondition validator that checks output contract
    
    This bridges the contract layer with the validator system.
    
    Args:
        expected_kind: Expected output kind (JSON, TEXT, etc.)
        schema: Optional JSON schema for validation
        strict_mode: If True, drift causes BLOCK instead of WARN
        
    Returns:
        PostconditionValidator that checks contract compliance
        
    Example:
        >>> registry.register_postcondition(
        ...     "fetch_user",
        ...     output_contract_postcondition(
        ...         expected_kind=ExpectedKind.JSON,
        ...         schema={"required": ["id", "name"]}
        ...     )
        ... )
    """
    def check(ctx: Dict[str, Any]) -> ValidationResult:
        """Check output against contract"""
        result = ctx.get("result")
        
        # If no result, skip validation (tool didn't execute)
        if result is None:
            return ValidationResult.success("No output to validate")
        
        # Use contract checker
        contract_result: ContractResult = check_output(
            value=result,
            expected_kind=expected_kind,
            schema=schema,
            strict_mode=strict_mode,
        )
        
        # Convert ContractResult to ValidationResult
        if contract_result.is_ok():
            return ValidationResult.success(
                "Output contract satisfied",
                validator="output_contract",
                code="CONTRACT_OK",
            )
        
        # Contract drift detected
        code = contract_result.drift_type.value.upper() if contract_result.drift_type else "CONTRACT_DRIFT"
        
        details = {
            "drift_type": contract_result.drift_type.value if contract_result.drift_type else None,
            "expected_kind": contract_result.expected_kind.value if contract_result.expected_kind else None,
            "observed_kind": contract_result.observed_kind,
            "reason": contract_result.reason,
        }
        
        # Add optional diagnostics
        if contract_result.parse_error:
            details["parse_error"] = contract_result.parse_error
        if contract_result.fields_missing:
            details["fields_missing"] = contract_result.fields_missing
        if contract_result.raw_excerpt:
            details["raw_excerpt"] = contract_result.raw_excerpt
        
        # Map contract decision to validation severity
        if contract_result.should_warn():
            return ValidationResult.warning(
                message=f"Contract drift: {contract_result.reason}",
                details=details,
                code=code,
                validator="output_contract",
            )
        else:  # should_block
            return ValidationResult.failure(
                message=f"Contract violation: {contract_result.reason}",
                details=details,
                code=code,
                validator="output_contract",
            )
    
    name = "output_contract"
    if expected_kind:
        name += f"_{expected_kind.value}"
    
    return PostconditionValidator(
        name=name,
        condition=check,
        code="CONTRACT_VIOLATION",
    )


def json_output_postcondition(
    schema: Optional[Dict[str, Any]] = None,
    strict_mode: bool = False,
) -> PostconditionValidator:
    """
    Convenience: Create postcondition that expects JSON output
    
    Args:
        schema: Optional JSON schema
        strict_mode: If True, drift causes BLOCK instead of WARN
        
    Returns:
        PostconditionValidator for JSON output
    """
    return output_contract_postcondition(
        expected_kind=ExpectedKind.JSON,
        schema=schema,
        strict_mode=strict_mode,
    )


def text_output_postcondition(strict_mode: bool = False) -> PostconditionValidator:
    """
    Convenience: Create postcondition that expects TEXT output
    
    Args:
        strict_mode: If True, drift causes BLOCK instead of WARN
        
    Returns:
        PostconditionValidator for TEXT output
    """
    return output_contract_postcondition(
        expected_kind=ExpectedKind.TEXT,
        strict_mode=strict_mode,
    )
