# failcore/core/validate/validator.py
"""
Core validator implementation with enhanced traceability and fail-fast support.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Union, Literal
from enum import Enum
from pathlib import Path


class ValidationType(str, Enum):
    """Validation type"""
    PRECONDITION = "precondition"
    POSTCONDITION = "postcondition"
    INVARIANT = "invariant"  # Reserved for future use


@dataclass
class ValidationContext:
    """
    Typed validation context to avoid KeyError issues.
    
    Provides structured access to validation data with defaults.
    """
    tool: str
    params: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    step_id: Optional[str] = None
    state: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ValidationContext:
        """Create from legacy dict context"""
        return cls(
            tool=data.get("tool", "unknown"),
            params=data.get("params", {}),
            result=data.get("result"),
            step_id=data.get("step_id"),
            state=data.get("state", {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for backward compatibility"""
        return {
            "tool": self.tool,
            "params": self.params,
            "result": self.result,
            "step_id": self.step_id,
            "state": self.state
        }


@dataclass
class ValidationResult:
    """
    Validation result with enhanced traceability.
    
    Now includes validator metadata for better debugging and aggregation.
    Severity determines the validation outcome:
    - "ok": Validation passed
    - "warn": Drift detected but non-critical (step continues)
    - "block": Critical violation (step blocked)
    
    The 'valid' field is derived from severity to avoid conflicts.
    """
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    severity: Literal["ok", "warn", "block"] = "ok"
    
    # Enhanced metadata
    validator: Optional[str] = None  # Validator name
    vtype: Optional[ValidationType] = None  # Validation type
    tool: Optional[str] = None  # Tool name
    code: Optional[str] = None  # Machine-readable error code
    
    @property
    def valid(self) -> bool:
        """
        Derived from severity to avoid conflicts.
        Only severity="block" is considered invalid.
        """
        return self.severity != "block"
    
    @classmethod
    def success(cls, message: str = "Validation passed", **kwargs) -> ValidationResult:
        """Create success result (severity="ok")"""
        return cls(message=message, severity="ok", **kwargs)
    
    @classmethod
    def warning(
        cls,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        **kwargs
    ) -> ValidationResult:
        """Create warning result (severity="warn", non-blocking)"""
        return cls(
            message=message,
            severity="warn",
            details=details or {},
            code=code,
            **kwargs
        )
    
    @classmethod
    def failure(
        cls, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        code: Optional[str] = None,
        **kwargs
    ) -> ValidationResult:
        """Create failure result (severity="block", blocking)"""
        return cls(
            message=message,
            severity="block",
            details=details or {},
            code=code,
            **kwargs
        )


class ValidationError(Exception):
    """Validation failure exception"""
    def __init__(self, message: str, results: List[ValidationResult]):
        super().__init__(message)
        self.results = results  # Changed to support multiple failures
    
    @property
    def result(self) -> Optional[ValidationResult]:
        """Get first failure (backward compatibility)"""
        return self.results[0] if self.results else None


class Validator(Protocol):
    """Validator protocol"""
    
    def validate(self, context: Dict[str, Any]) -> ValidationResult:
        """
        Execute validation.
        
        Args:
            context: Validation context (includes step, params, result, etc.)
            
        Returns:
            Validation result
        """
        ...


@dataclass
class PreconditionValidator:
    """
    Precondition validator.
    
    Checks conditions before tool execution, for example:
    - File existence
    - Parameter validity
    - Resource availability
    """
    name: str
    condition: Callable[[Dict[str, Any]], Union[bool, ValidationResult]]  # Suggestion #7
    message: str = ""
    code: Optional[str] = None  # Machine-readable error code
    
    def validate(self, context: Dict[str, Any]) -> ValidationResult:
        """Execute validation with enhanced result handling"""
        # Normalize context (Suggestion #4)
        if not isinstance(context, ValidationContext):
            ctx_obj = ValidationContext.from_dict(context)
        else:
            ctx_obj = context
        
        try:
            result = self.condition(context)
            
            # Suggestion #7: Support returning ValidationResult directly
            if isinstance(result, ValidationResult):
                # Enrich with metadata
                result.validator = result.validator or self.name
                result.vtype = result.vtype or ValidationType.PRECONDITION
                result.tool = result.tool or ctx_obj.tool
                result.code = result.code or self.code
                return result
            
            # Traditional bool result
            if result:
                return ValidationResult.success(
                    f"Precondition '{self.name}' satisfied",
                    validator=self.name,
                    vtype=ValidationType.PRECONDITION,
                    tool=ctx_obj.tool
                )
            else:
                msg = self.message or f"Precondition '{self.name}' not satisfied"
                return ValidationResult.failure(
                    msg,
                    details={"condition": self.name},
                    code=self.code or "PRECONDITION_FAILED",
                    validator=self.name,
                    vtype=ValidationType.PRECONDITION,
                    tool=ctx_obj.tool
                )
        except Exception as e:
            return ValidationResult.failure(
                f"Precondition '{self.name}' check failed: {e}",
                {"condition": self.name, "error": str(e)},
                code=self.code or "PRECONDITION_ERROR",
                validator=self.name,
                vtype=ValidationType.PRECONDITION,
                tool=ctx_obj.tool
            )


@dataclass
class PostconditionValidator:
    """
    Postcondition validator.
    
    Checks results after tool execution, for example:
    - File creation
    - Return value correctness
    - Side effect compliance
    """
    name: str
    condition: Callable[[Dict[str, Any]], Union[bool, ValidationResult]]  # Suggestion #7
    message: str = ""
    code: Optional[str] = None
    
    def validate(self, context: Dict[str, Any]) -> ValidationResult:
        """Execute validation with enhanced result handling"""
        # Normalize context
        if not isinstance(context, ValidationContext):
            ctx_obj = ValidationContext.from_dict(context)
        else:
            ctx_obj = context
        
        try:
            result = self.condition(context)
            
            # Support returning ValidationResult directly
            if isinstance(result, ValidationResult):
                result.validator = result.validator or self.name
                result.vtype = result.vtype or ValidationType.POSTCONDITION
                result.tool = result.tool or ctx_obj.tool
                result.code = result.code or self.code
                return result
            
            if result:
                return ValidationResult.success(
                    f"Postcondition '{self.name}' satisfied",
                    validator=self.name,
                    vtype=ValidationType.POSTCONDITION,
                    tool=ctx_obj.tool
                )
            else:
                msg = self.message or f"Postcondition '{self.name}' not satisfied"
                return ValidationResult.failure(
                    msg,
                    details={"condition": self.name},
                    code=self.code or "POSTCONDITION_FAILED",
                    validator=self.name,
                    vtype=ValidationType.POSTCONDITION,
                    tool=ctx_obj.tool
                )
        except Exception as e:
            return ValidationResult.failure(
                f"Postcondition '{self.name}' check failed: {e}",
                {"condition": self.name, "error": str(e)},
                code=self.code or "POSTCONDITION_ERROR",
                validator=self.name,
                vtype=ValidationType.POSTCONDITION,
                tool=ctx_obj.tool
            )


@dataclass
class ToolValidators:
    """
    Container for tool validators (Suggestion #1).
    
    More extensible than tuple[List, List] - easy to add invariants/metadata later.
    """
    pre: List[Validator] = field(default_factory=list)
    post: List[Validator] = field(default_factory=list)
    # Future: invariants, metadata, etc.


ValidationMode = Literal["all", "fail_fast"]


class ValidatorRegistry:
    """
    Validator registry with prefix matching and fail-fast support.
    """
    
    def __init__(self) -> None:
        # Suggestion #1: Use ToolValidators instead of tuple
        self._validators: Dict[str, ToolValidators] = {}
        # Suggestion #8: Prefix patterns (e.g., "file.*")
        self._prefix_validators: Dict[str, ToolValidators] = {}
    
    def register_precondition(
        self, 
        tool_pattern: str, 
        validator: Validator,
        is_prefix: bool = False
    ) -> None:
        """
        Register precondition validator.
        
        Args:
            tool_pattern: Tool name or prefix pattern (e.g., "file.*")
            validator: Validator instance
            is_prefix: If True, treats tool_pattern as prefix (matches "file.*")
        """
        if is_prefix or tool_pattern.endswith(".*"):
            # Prefix pattern
            prefix = tool_pattern.rstrip(".*")
            if prefix not in self._prefix_validators:
                self._prefix_validators[prefix] = ToolValidators()
            self._prefix_validators[prefix].pre.append(validator)
        else:
            # Exact match
            if tool_pattern not in self._validators:
                self._validators[tool_pattern] = ToolValidators()
            self._validators[tool_pattern].pre.append(validator)
    
    def register_postcondition(
        self, 
        tool_pattern: str, 
        validator: Validator,
        is_prefix: bool = False
    ) -> None:
        """Register postcondition validator"""
        if is_prefix or tool_pattern.endswith(".*"):
            prefix = tool_pattern.rstrip(".*")
            if prefix not in self._prefix_validators:
                self._prefix_validators[prefix] = ToolValidators()
            self._prefix_validators[prefix].post.append(validator)
        else:
            if tool_pattern not in self._validators:
                self._validators[tool_pattern] = ToolValidators()
            self._validators[tool_pattern].post.append(validator)
    
    def get_preconditions(self, tool_name: str) -> List[Validator]:
        """
        Get precondition validators (exact + prefix matches).
        
        Priority order:
        1. Exact match first
        2. Longest prefix match next
        3. Shorter prefix matches
        
        All matched validators are returned (stacked).
        """
        validators = []
        
        # 1. Exact match first
        if tool_name in self._validators:
            validators.extend(self._validators[tool_name].pre)
        
        # 2. Prefix matches (sorted by length DESC - longest first)
        prefix_matches = []
        for prefix, tool_validators in self._prefix_validators.items():
            if tool_name.startswith(prefix + ".") or tool_name == prefix:
                prefix_matches.append((len(prefix), prefix, tool_validators))
        
        # Sort by prefix length descending (longest prefix first)
        prefix_matches.sort(reverse=True, key=lambda x: x[0])
        
        for _, _, tool_validators in prefix_matches:
            validators.extend(tool_validators.pre)
        
        return validators
    
    def get_postconditions(self, tool_name: str) -> List[Validator]:
        """
        Get postcondition validators (exact + prefix matches).
        
        Priority order:
        1. Exact match first
        2. Longest prefix match next
        3. Shorter prefix matches
        
        All matched validators are returned (stacked).
        """
        validators = []
        
        # 1. Exact match first
        if tool_name in self._validators:
            validators.extend(self._validators[tool_name].post)
        
        # 2. Prefix matches (sorted by length DESC - longest first)
        prefix_matches = []
        for prefix, tool_validators in self._prefix_validators.items():
            if tool_name.startswith(prefix + ".") or tool_name == prefix:
                prefix_matches.append((len(prefix), prefix, tool_validators))
        
        # Sort by prefix length descending (longest prefix first)
        prefix_matches.sort(reverse=True, key=lambda x: x[0])
        
        for _, _, tool_validators in prefix_matches:
            validators.extend(tool_validators.post)
        
        return validators
    
    def validate_preconditions(
        self, 
        tool_name: str, 
        context: Dict[str, Any],
        mode: ValidationMode = "fail_fast"
    ) -> List[ValidationResult]:
        """
        Validate all preconditions.
        
        Args:
            tool_name: Tool name
            context: Validation context
            mode: Validation mode
                - "fail_fast": Stop at first BLOCK (severity="block")
                              WARN (severity="warn") does NOT stop
                - "all": Collect all results (WARN + BLOCK)
        
        Returns:
            List of validation results ordered by execution
        """
        validators = self.get_preconditions(tool_name)
        results = []
        
        for v in validators:
            result = v.validate(context)
            results.append(result)
            
            # fail_fast only stops on BLOCK, not WARN
            if mode == "fail_fast" and result.severity == "block":
                break
        
        return results
    
    def validate_postconditions(
        self, 
        tool_name: str, 
        context: Dict[str, Any],
        mode: ValidationMode = "fail_fast"
    ) -> List[ValidationResult]:
        """
        Validate all postconditions.
        
        Args:
            tool_name: Tool name
            context: Validation context
            mode: Validation mode
                - "fail_fast": Stop at first BLOCK (severity="block")
                              WARN (severity="warn") does NOT stop
                - "all": Collect all results (WARN + BLOCK)
        
        Returns:
            List of validation results ordered by execution
        """
        validators = self.get_postconditions(tool_name)
        results = []
        
        for v in validators:
            result = v.validate(context)
            results.append(result)
            
            # fail_fast only stops on BLOCK, not WARN
            if mode == "fail_fast" and result.severity == "block":
                break
        
        return results
    
    def ensure_preconditions(self, tool_name: str, context: Dict[str, Any]) -> None:
        """
        Validate preconditions and raise ValidationError on failure.
        
        Suggestion #9: Unified entry point for runtime enforcement.
        """
        results = self.validate_preconditions(tool_name, context, mode="fail_fast")
        failures = [r for r in results if not r.valid]
        
        if failures:
            first = failures[0]
            raise ValidationError(
                f"Precondition failed for '{tool_name}': {first.message}",
                failures
            )
    
    def ensure_postconditions(self, tool_name: str, context: Dict[str, Any]) -> None:
        """
        Validate postconditions and raise ValidationError on failure.
        
        Suggestion #9: Unified entry point for runtime enforcement.
        """
        results = self.validate_postconditions(tool_name, context, mode="fail_fast")
        failures = [r for r in results if not r.valid]
        
        if failures:
            first = failures[0]
            raise ValidationError(
                f"Postcondition failed for '{tool_name}': {first.message}",
                failures
            )
    
    def has_validators(self, tool_name: str) -> bool:
        """Check if tool has any validators"""
        pre = self.get_preconditions(tool_name)
        post = self.get_postconditions(tool_name)
        return len(pre) > 0 or len(post) > 0
    
    def has_preconditions(self, tool_name: str) -> bool:
        """Check if tool has preconditions"""
        return len(self.get_preconditions(tool_name)) > 0


# ===== Helper: Path normalization (Suggestion #6) =====

def _normalize_path(path_str: str) -> Path:
    """
    Normalize path with expanduser and resolve.
    
    Suggestion #6: Use pathlib for consistent path handling.
    """
    try:
        return Path(path_str).expanduser().resolve()
    except (ValueError, OSError):
        # If path is invalid or cannot be resolved, return as-is
        return Path(path_str).expanduser()


# ===== Common precondition validators =====

def file_exists_precondition(param_name: str = "path") -> PreconditionValidator:
    """
    Precondition: File must exist.
    
    Suggestions #5 & #6: Show actual value and use pathlib.
    """
    def check(ctx: Dict[str, Any]) -> ValidationResult:
        value = ctx.get("params", {}).get(param_name, "")
        if not value:
            return ValidationResult.failure(
                f"Parameter '{param_name}' is empty",
                {"param": param_name, "value": value},
                code="PARAM_EMPTY"
            )
        
        path = _normalize_path(value)
        if path.is_file():
            return ValidationResult.success()
        else:
            return ValidationResult.failure(
                f"File does not exist: {value}",
                {"param": param_name, "value": str(value), "resolved": str(path)},
                code="FILE_NOT_FOUND"
            )
    
    return PreconditionValidator(
        name=f"file_exists_{param_name}",
        condition=check,
        code="FILE_NOT_FOUND"
    )


def file_not_exists_precondition(param_name: str = "path") -> PreconditionValidator:
    """
    Precondition: File must NOT exist.
    
    Suggestions #5 & #6: Show actual value and use pathlib.
    """
    def check(ctx: Dict[str, Any]) -> ValidationResult:
        value = ctx.get("params", {}).get(param_name, "")
        if not value:
            return ValidationResult.failure(
                f"Parameter '{param_name}' is empty",
                {"param": param_name, "value": value},
                code="PARAM_EMPTY"
            )
        
        path = _normalize_path(value)
        if not path.exists():
            return ValidationResult.success()
        else:
            return ValidationResult.failure(
                f"File already exists: {value}",
                {"param": param_name, "value": str(value), "resolved": str(path)},
                code="FILE_ALREADY_EXISTS"
            )
    
    return PreconditionValidator(
        name=f"file_not_exists_{param_name}",
        condition=check,
        code="FILE_ALREADY_EXISTS"
    )


def dir_exists_precondition(param_name: str = "path") -> PreconditionValidator:
    """
    Precondition: Directory must exist.
    
    Suggestions #5 & #6: Show actual value and use pathlib.
    """
    def check(ctx: Dict[str, Any]) -> ValidationResult:
        value = ctx.get("params", {}).get(param_name, "")
        if not value:
            return ValidationResult.failure(
                f"Parameter '{param_name}' is empty",
                {"param": param_name, "value": value},
                code="PARAM_EMPTY"
            )
        
        path = _normalize_path(value)
        if path.is_dir():
            return ValidationResult.success()
        else:
            return ValidationResult.failure(
                f"Directory does not exist: {value}",
                {"param": param_name, "value": str(value), "resolved": str(path)},
                code="DIR_NOT_FOUND"
            )
    
    return PreconditionValidator(
        name=f"dir_exists_{param_name}",
        condition=check,
        code="DIR_NOT_FOUND"
    )


def param_not_empty_precondition(param_name: str) -> PreconditionValidator:
    """
    Precondition: Parameter must not be empty.
    
    Suggestion #5: Show actual value in message.
    """
    def check(ctx: Dict[str, Any]) -> ValidationResult:
        value = ctx.get("params", {}).get(param_name)
        if value:
            return ValidationResult.success()
        else:
            return ValidationResult.failure(
                f"Parameter '{param_name}' is empty or missing (got: {repr(value)})",
                {"param": param_name, "value": value},
                code="PARAM_EMPTY"
            )
    
    return PreconditionValidator(
        name=f"param_not_empty_{param_name}",
        condition=check,
        code="PARAM_EMPTY"
    )

