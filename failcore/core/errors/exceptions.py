# failcore/errors/exceptions.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Mapping, TypedDict

from . import codes


class _ToolResultLike(TypedDict, total=False):
    status: Any
    error: Any
    message: str


def _safe_str(x: Any) -> str:
    try:
        return str(x)
    except Exception:
        return "<unstringifiable>"


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return default


def _get_mapping(d: Any, key: str, default: Any = None) -> Any:
    if isinstance(d, Mapping):
        return d.get(key, default)
    return default


def _normalize_error_code(code: Any) -> str:
    """
    Keep error_code stable and finite.
    Unknown upstream codes should not explode UI/report taxonomy.
    
    Preserves well-defined error codes across three categories:
    - Security violations (SECURITY_CODES)
    - Operational states (OPERATIONAL_CODES)  
    - Fallback categories (DEFAULT_FALLBACK_CODES)
    """
    c = _safe_str(code or codes.UNKNOWN).strip() or codes.UNKNOWN

    # Keep all explicit security codes as-is
    if c in codes.SECURITY_CODES:
        return c
    
    # Keep operational codes (registry, validation, execution)
    if c in codes.OPERATIONAL_CODES:
        return c

    # Keep common fallback categories
    if c in codes.DEFAULT_FALLBACK_CODES:
        return c

    # Unknown code from upstream - downgrade for stability
    return codes.UNKNOWN


@dataclass
class FailCoreError(Exception):
    """
    The one public exception type for FailCore "easy" APIs.
    
    LLM-Friendly Design:
    - suggestion: Machine-actionable fix guidance for AI agents
    - hint: Human-readable explanation
    - remediation: Structured fix instructions with template variables
    """
    message: str
    error_code: str = codes.UNKNOWN
    error_type: str = "FAILCORE_ERROR"  # e.g. VALIDATION_ERROR / EXECUTION_ERROR
    phase: str = "unknown"              # validate / execute / runtime
    retryable: bool = False
    details: Dict[str, Any] = field(default_factory=dict)
    cause: Optional[BaseException] = None
    
    # LLM-friendly fields (first-class citizens)
    suggestion: Optional[str] = None      # Quick fix suggestion for AI/human
    hint: Optional[str] = None            # Additional context/explanation
    remediation: Optional[Dict[str, Any]] = None  # Structured fix with template vars

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        """
        Render error with suggestion for both human and LLM consumption.
        Format: [ERROR_CODE] message\n[Suggestion] fix_guidance
        """
        result = f"[{self.error_code}] {self.message}"
        
        # Add suggestion prominently if available
        if self.suggestion:
            result += f"\n\n[Suggestion] {self.suggestion}"
        
        # Add hint if available
        if self.hint:
            result += f"\n[Hint] {self.hint}"
        
        # Add remediation (structured fix instructions) if available
        if self.remediation and isinstance(self.remediation, dict):
            if "template" in self.remediation:
                template = self.remediation.get("template", "")
                vars_dict = self.remediation.get("vars", {})
                result += f"\n[Remediation] {template}"
                if vars_dict:
                    result += f" (vars: {vars_dict})"
            else:
                result += f"\n[Remediation] {self.remediation}"
        
        return result

    @property
    def is_security(self) -> bool:
        return self.error_code in codes.SECURITY_CODES

    def to_dict(self) -> Dict[str, Any]:
        """Export error as dict (includes LLM-friendly fields)"""
        result = {
            "type": self.error_type,
            "error_code": self.error_code,
            "message": self.message,
            "phase": self.phase,
            "retryable": self.retryable,
            "details": self.details,
        }
        
        # Include LLM-friendly fields if present
        if self.suggestion:
            result["suggestion"] = self.suggestion
        if self.hint:
            result["hint"] = self.hint
        if self.remediation:
            result["remediation"] = self.remediation
        
        return result

    # -------- factories --------

    @classmethod
    def from_tool_result(cls, result: Any) -> "FailCoreError":
        err = _get_attr(result, "error", None)
        status = _get_attr(result, "status", None)

        if err is None:
            msg = _safe_str(_get_attr(result, "message", None) or "Tool call failed.")
            return cls(
                message=msg,
                error_code=codes.UNKNOWN,
                error_type="TOOL_ERROR",
                phase="unknown",
                retryable=False,
                details={"status": _safe_str(status)},
            )

        # dict-like error
        if isinstance(err, Mapping):
            raw_code = _get_mapping(err, "error_code", codes.UNKNOWN)
            code = _normalize_error_code(raw_code)

            error_type = _get_mapping(err, "type", "TOOL_ERROR") or "TOOL_ERROR"
            message = _get_mapping(err, "message", None) or "Tool call failed."
            phase = _get_mapping(err, "phase", None) or _get_mapping(err, "where", None) or "unknown"
            retryable = bool(_get_mapping(err, "retryable", False))
            
            # CRITICAL: StepError uses "detail" (singular), not "details" (plural)
            # Try both for backward compatibility
            details = dict(_get_mapping(err, "detail", {}) or _get_mapping(err, "details", {}) or {})
            details.setdefault("status", _safe_str(status))

            # preserve original upstream code if we downgraded
            if code == codes.UNKNOWN and raw_code not in (None, "", codes.UNKNOWN):
                details.setdefault("upstream_error_code", _safe_str(raw_code))
            
            # Scheme 3: Extract LLM-friendly fields from details dict
            # Since we already merged detail/details above, extract from there
            suggestion = details.get("suggestion") if isinstance(details, dict) else None
            remediation = details.get("remediation") if isinstance(details, dict) else None

            return cls(
                message=_safe_str(message),
                error_code=code,
                error_type=_safe_str(error_type),
                phase=_safe_str(phase),
                retryable=retryable,
                details=details,
                suggestion=_safe_str(suggestion) if suggestion else None,
                hint=None,  # Could be added later
                remediation=remediation if isinstance(remediation, dict) else None,
            )

        # object-like error (e.g., StepError dataclass)
        raw_code = _get_attr(err, "error_code", codes.UNKNOWN)
        code = _normalize_error_code(raw_code)

        error_type = _get_attr(err, "type", "TOOL_ERROR") or "TOOL_ERROR"
        message = _get_attr(err, "message", None) or "Tool call failed."
        phase = _get_attr(err, "phase", None) or _get_attr(err, "where", None) or "unknown"
        retryable = bool(_get_attr(err, "retryable", False))
        
        # CRITICAL: StepError uses "detail" (singular), not "details" (plural)
        details = _get_attr(err, "detail", None) or _get_attr(err, "details", None)
        if not isinstance(details, dict):
            details = {}
        details.setdefault("status", _safe_str(status))

        if code == codes.UNKNOWN and raw_code not in (None, "", codes.UNKNOWN):
            details.setdefault("upstream_error_code", _safe_str(raw_code))
        
        # Scheme 3: Extract LLM-friendly fields from detail dict
        suggestion = details.get("suggestion") if isinstance(details, dict) else None
        remediation = details.get("remediation") if isinstance(details, dict) else None

        return cls(
            message=_safe_str(message),
            error_code=code,
            error_type=_safe_str(error_type),
            phase=_safe_str(phase),
            retryable=retryable,
            details=details,
            suggestion=_safe_str(suggestion) if suggestion else None,
            hint=None,  # Could be added later
            remediation=remediation if isinstance(remediation, dict) else None,
        )

    @classmethod
    def validation(
        cls,
        message: str,
        *,
        error_code: str = codes.PRECONDITION_FAILED,
        details: Optional[Dict[str, Any]] = None,
    ) -> "FailCoreError":
        return cls(
            message=message,
            error_code=_normalize_error_code(error_code),
            error_type="VALIDATION_ERROR",
            phase="validate",
            retryable=False,
            details=details or {},
        )

    @classmethod
    def policy_denied(
        cls,
        message: str,
        *,
        error_code: str = codes.POLICY_DENIED,
        details: Optional[Dict[str, Any]] = None,
    ) -> "FailCoreError":
        return cls(
            message=message,
            error_code=_normalize_error_code(error_code),
            error_type="POLICY_DENIED",
            phase="validate",
            retryable=False,
            details=details or {},
        )

    @classmethod
    def execution_failed(
        cls,
        message: str,
        *,
        error_code: str = codes.TOOL_EXECUTION_FAILED,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[BaseException] = None,
    ) -> "FailCoreError":
        return cls(
            message=message,
            error_code=_normalize_error_code(error_code),
            error_type="EXECUTION_ERROR",
            phase="execute",
            retryable=retryable,
            details=details or {},
            cause=cause,
        )
