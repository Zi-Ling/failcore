# failcore/core/validate/validators/contract.py
"""
Contract-based validators for output validation

Bridges contract/ layer with validate/ layer.
"""

from typing import Any, Dict, Optional
from failcore.core.contract import ExpectedKind, check_output, ContractResult
from ..validator import PostconditionValidator, ValidationResult


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
