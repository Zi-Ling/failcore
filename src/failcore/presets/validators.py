# failcore/presets/validators.py
"""
Validator Presets - Ready-to-use validator configurations

These presets configure ValidatorRegistry with common validation rules.
"""

from typing import List
from ..core.validate.validator import (
    ValidatorRegistry,
    PreconditionValidator,
    ValidationResult,
    file_exists_precondition,
    file_not_exists_precondition,
    dir_exists_precondition,
    param_not_empty_precondition,
)


# ===== Helper: Multi-param validators (Suggestion #1) =====

def file_path_precondition(
    *param_names: str,
    must_exist: str = "exists"
) -> PreconditionValidator:
    """
    File path precondition with fallback parameter names and three-state existence check.
    
    Suggestion #1: Support multiple param names to catch variations like:
    - path, relative_path, file_path, filename, dst, output_path
    
    Suggestion #2 (0.1.0a2): Three-state existence semantics:
    - "exists": File MUST exist (for read operations)
    - "not_exists": File MUST NOT exist (for create operations)
    - "any": Path must be valid, but file may or may not exist (for write/overwrite)
    
    Args:
        *param_names: Parameter names to check (first found is used)
        must_exist: Existence requirement - "exists", "not_exists", or "any"
    
    Returns:
        PreconditionValidator
    
    Example:
        >>> # For read: must exist
        >>> validator = file_path_precondition("path", must_exist="exists")
        >>> # For create: must NOT exist
        >>> validator = file_path_precondition("path", must_exist="not_exists")
        >>> # For write: either is OK
        >>> validator = file_path_precondition("path", must_exist="any")
    """
    if not param_names:
        param_names = ("path",)
    
    # Validate must_exist parameter
    if must_exist not in ("exists", "not_exists", "any"):
        raise ValueError(f"must_exist must be 'exists', 'not_exists', or 'any', got: {must_exist}")
    
    def check(ctx) -> ValidationResult:
        params = ctx.get("params", {})
        
        # Suggestion #7: Find first NON-EMPTY matching param
        # This prevents bugs where path="" is found before file_path="/valid"
        found_param = None
        found_value = None
        for name in param_names:
            if name in params:
                value = params[name]
                # Prioritize non-empty values
                if value:
                    found_param = name
                    found_value = value
                    break
                # Remember first param even if empty (fallback)
                elif found_param is None:
                    found_param = name
                    found_value = value
        
        if found_param is None:
            return ValidationResult.failure(
                f"Missing file path parameter (expected one of: {', '.join(param_names)})",
                {"expected_params": list(param_names)},
                code="MISSING_FILE_PATH_PARAM"
            )
        
        if not found_value:
            return ValidationResult.failure(
                f"Parameter '{found_param}' is empty",
                {"param": found_param, "value": found_value},
                code="PARAM_EMPTY"
            )
        
        # Check existence based on mode
        if must_exist == "exists":
            return file_exists_precondition(found_param).validate(ctx)
        elif must_exist == "not_exists":
            return file_not_exists_precondition(found_param).validate(ctx)
        else:  # "any"
            # Only validate that path is not empty (already done above)
            return ValidationResult.success()
    
    names_str = "_or_".join(param_names[:2])  # Avoid too long names
    return PreconditionValidator(
        name=f"file_path_{must_exist}_{names_str}",
        condition=check,
        code={
            "exists": "FILE_NOT_FOUND",
            "not_exists": "FILE_ALREADY_EXISTS",
            "any": "PARAM_EMPTY"
        }.get(must_exist, "FILE_CHECK_FAILED")
    )


def fs_safe() -> ValidatorRegistry:
    """
    File system safety validator preset
    
    Common file preconditions:
    - Read operations: file must exist
    - Write operations: path/content not empty, allows overwrite (0.1.0a2)
    - Create operations: file must not already exist
    - Directory operations: directory must exist
    
    0.1.0a2 IMPROVEMENTS:
    - Write operations now use must_exist="any" (allows both new and existing files)
    - No longer incorrectly rejects overwrites to existing files
    - Prefix patterns use pure string matching (no glob wildcards)
    
    IMPORTANT LIMITATIONS (Suggestion #8):
    - Write semantics (overwrite/append/mode) are NOT fully validated yet
    - Does NOT prevent silent overwrites (by design for flexibility)
    - Does NOT distinguish between write/append modes
    - Future versions will add mode-specific checks
    
    Suggestion #2: Uses prefix patterns for auto-matching new tools.
    
    Returns:
        ValidatorRegistry: Configured validator registry
    
    Example:
        >>> from failcore import Session, presets
        >>> session = Session(validator=presets.fs_safe())
    """
    registry = ValidatorRegistry()
    
    # Suggestion #2: Use prefix patterns instead of hardcoded tool names
    # Note: Prefix is pure string prefix, NOT glob. "file.read" matches "file.read_text", etc.
    
    # Read file tools: file must exist (matches file.read, file.read_text, etc.)
    registry.register_precondition(
        "file.read",  # Matches file.read, file.read_text, file.read_json, etc.
        file_path_precondition("path", "relative_path", "file_path", "filename", must_exist="exists"),
        is_prefix=True
    )
    
    # Legacy exact matches for backward compatibility
    registry.register_precondition(
        "read_file",
        file_path_precondition("path", "relative_path", "file_path", "filename", must_exist="exists")
    )
    
    # Write file tools: path and content not empty
    # Suggestion #1: Support multiple param name variations
    registry.register_precondition(
        "file.write",  # Matches file.write, file.write_text, file.write_json, etc.
        file_path_precondition(
            "path", "relative_path", "file_path", "output_path", "dst",
            must_exist="any"  # Allow any (overwrite or new file)
        ),
        is_prefix=True
    )
    
    registry.register_precondition(
        "file.write",
        param_not_empty_precondition("content"),
        is_prefix=True
    )
    
    # Legacy exact matches
    registry.register_precondition(
        "write_file",
        param_not_empty_precondition("path")
    )
    registry.register_precondition(
        "write_file",
        param_not_empty_precondition("content")
    )
    
    # Suggestion #3: TODO - Add overwrite/append/mode checks
    # Future: Add validators for:
    # - overwrite=False => file must not exist
    # - append=True => file must exist
    # - mode checks (e.g., "w", "a", "r+")
    
    # Create file: file must not already exist
    registry.register_precondition(
        "file.create",  # Pure prefix, no glob
        file_path_precondition("path", "relative_path", "filename", must_exist="not_exists"),
        is_prefix=True
    )
    
    registry.register_precondition(
        "create_file",
        file_not_exists_precondition("path")
    )
    
    # Directory operations: directory must exist
    registry.register_precondition(
        "dir.list",  # Pure prefix, no glob
        dir_exists_precondition("path"),
        is_prefix=True
    )
    
    registry.register_precondition(
        "list_dir",
        dir_exists_precondition("path")
    )
    
    return registry


def net_safe() -> ValidatorRegistry:
    """
    Network safety validator preset
    
    Network validations:
    - All HTTP requests: URL must not be empty
    - POST/PUT/PATCH: body/data must not be empty (Suggestion #4)
    - Timeout checks (future)
    - Domain whitelist (future)
    
    KNOWN LIMITATIONS:
    - Suggestion #10: POST with query params (POST ?a=b) may be incorrectly rejected
      if body/data/json is not provided. Future versions may check Content-Type.
    - Suggestion #9: Empty binary data (b"") may be incorrectly flagged as missing.
      "not empty" currently uses truthy check, not None vs empty distinction.
    
    Returns:
        ValidatorRegistry: Configured validator registry
    
    Example:
        >>> session = Session(validator=presets.net_safe())
    """
    registry = ValidatorRegistry()
    
    # All HTTP requests: URL must not be empty
    registry.register_precondition(
        "http",  # Pure prefix: matches http.get, http.post, http_request, etc.
        param_not_empty_precondition("url"),
        is_prefix=True
    )
    
    # Legacy exact matches
    for tool in ["http_get", "http_post", "http_put", "http_patch", "http_delete"]:
        registry.register_precondition(
            tool,
            param_not_empty_precondition("url")
        )
    
    # Suggestion #4: POST/PUT/PATCH require body/data
    def body_required(ctx) -> ValidationResult:
        """Check if body or data parameter exists for write operations"""
        params = ctx.get("params", {})
        body = params.get("body") or params.get("data") or params.get("json")
        
        if body:
            return ValidationResult.success()
        else:
            return ValidationResult.failure(
                "POST/PUT/PATCH operations require body/data/json parameter",
                {"params": list(params.keys())},
                code="BODY_REQUIRED"
            )
    
    body_validator = PreconditionValidator(
        name="http_body_required",
        condition=body_required,
        code="BODY_REQUIRED"
    )
    
    # POST/PUT/PATCH: require body (pure prefix, no glob)
    for pattern in ["http.post", "http.put", "http.patch"]:
        registry.register_precondition(pattern, body_validator, is_prefix=True)
    
    for tool in ["http_post", "http_put", "http_patch"]:
        registry.register_precondition(tool, body_validator)
    
    return registry


__all__ = ["fs_safe", "net_safe", "file_path_precondition"]

