# failcore/presets/builtin.py
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


# ===== Helper: Multi-param builtin (Suggestion #1) =====

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


def fs_safe(strict: bool = False, sandbox_root: str = None) -> ValidatorRegistry:
    """
    File system safety validator preset
    
    Common file preconditions:
    - Read operations: file must exist
    - Write operations: path/content not empty, allows overwrite (0.1.0a2)
    - Create operations: file must not already exist
    - Directory operations: directory must exist
    
    v0.1.2+ SECURITY ENHANCEMENTS:
    - strict=True: Enables path traversal defense (../ attack prevention)
    - strict=True: Enforces sandbox boundary (symlink resolution)
    - strict=True: Prevents directory escape attempts
    
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
    
    Args:
        strict: Enable strict security mode (path traversal defense, sandbox enforcement)
        sandbox_root: Sandbox root directory (uses cwd if None, only relevant when strict=True)
    
    Returns:
        ValidatorRegistry: Configured validator registry
    
    Example:
        >>> from failcore import Session, presets
        >>> # Development: basic checks
        >>> session = Session(validator=presets.fs_safe())
        >>> 
        >>> # Production: strict security
        >>> session = Session(validator=presets.fs_safe(strict=True))
    """
    import os
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
    # Future: Add builtin for:
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
    
    # Strict mode: Add security checks (v0.1.2+)
    if strict:
        from ..core.validate.builtin.security import path_traversal_precondition
        
        # Determine sandbox root
        if sandbox_root is None:
            sandbox_root = os.getcwd()
        
        # File operation tools that need path traversal checks
        file_ops_tools = [
            ("file.read", True),    # (tool, is_prefix)
            ("file.write", True),
            ("file.create", True),
            ("file.delete", True),
            ("read_file", False),
            ("write_file", False),
            ("create_file", False),
            ("delete_file", False),
        ]
        
        traversal_checker = path_traversal_precondition(
            "path", "relative_path", "file_path", "filename", "output_path", "dst",
            sandbox_root=sandbox_root
        )
        
        for tool, is_prefix in file_ops_tools:
            registry.register_precondition(tool, traversal_checker, is_prefix=is_prefix)
    
    return registry


def net_safe(
    strict: bool = False,
    allowed_domains: List[str] = None,
    block_internal: bool = True
) -> ValidatorRegistry:
    """
    Network safety validator preset
    
    Network validations:
    - All HTTP requests: URL must not be empty
    - POST/PUT/PATCH: body/data must not be empty (Suggestion #4)
    - v0.1.3+: Protocol whitelist (http/https only)
    - v0.1.3+: SSRF prevention (block internal IPs)
    - v0.1.3+: Domain whitelist (optional)
    
    KNOWN LIMITATIONS:
    - Suggestion #10: POST with query params (POST ?a=b) may be incorrectly rejected
      if body/data/json is not provided. Future versions may check Content-Type.
    - Suggestion #9: Empty binary data (b"") may be incorrectly flagged as missing.
      "not empty" currently uses truthy check, not None vs empty distinction.
    
    Args:
        strict: Enable strict security mode (protocol + SSRF checks)
        allowed_domains: Domain whitelist (e.g., ["api.github.com", "*.openai.com"])
        block_internal: Block access to internal/private IPs (default: True)
    
    Returns:
        ValidatorRegistry: Configured validator registry
    
    Example:
        >>> # Development: basic checks
        >>> session = Session(validator=presets.net_safe())
        >>> 
        >>> # Production: strict security + domain whitelist
        >>> session = Session(validator=presets.net_safe(
        ...     strict=True,
        ...     allowed_domains=["api.github.com", "*.openai.com"]
        ... ))
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
    
    # Strict mode: Add security checks (v0.1.3+)
    if strict:
        from ..core.validate.builtin.network import (
            url_safe_precondition,
            internal_ip_block_precondition,
            domain_whitelist_precondition,
        )
        
        http_tools = [
            ("http", True),  # (tool, is_prefix)
            ("http_get", False),
            ("http_post", False),
            ("http_put", False),
            ("http_patch", False),
            ("http_delete", False),
            ("fetch", False),
            ("fetch_url", False),
        ]
        
        # Protocol whitelist (http/https only)
        url_checker = url_safe_precondition("url")
        for tool, is_prefix in http_tools:
            registry.register_precondition(tool, url_checker, is_prefix=is_prefix)
        
        # SSRF prevention (block internal IPs)
        if block_internal:
            internal_blocker = internal_ip_block_precondition("url")
            for tool, is_prefix in http_tools:
                registry.register_precondition(tool, internal_blocker, is_prefix=is_prefix)
        
        # Domain whitelist (optional)
        if allowed_domains:
            domain_checker = domain_whitelist_precondition("url", allowed_domains=allowed_domains)
            for tool, is_prefix in http_tools:
                registry.register_precondition(tool, domain_checker, is_prefix=is_prefix)
    
    return registry


def fs_safe_sandbox(sandbox_root: str = None) -> ValidatorRegistry:
    """
    Deprecated: Use fs_safe(strict=True) instead
    
    This function is maintained for backward compatibility with v0.1.2.
    New code should use fs_safe(strict=True, sandbox_root=...) instead.
    
    Args:
        sandbox_root: Sandbox root directory (uses cwd if None)
    
    Returns:
        ValidatorRegistry: Configured validator registry with strict security
    
    Example (deprecated):
        >>> session = Session(validator=presets.fs_safe_sandbox("/app/workspace"))
    
    Example (recommended):
        >>> session = Session(validator=presets.fs_safe(strict=True, sandbox_root="/app/workspace"))
    """
    import warnings
    warnings.warn(
        "fs_safe_sandbox() is deprecated, use fs_safe(strict=True) instead",
        DeprecationWarning,
        stacklevel=2
    )
    return fs_safe(strict=True, sandbox_root=sandbox_root)


def resource_limited(
    max_file_mb: int = 10,
    max_payload_mb: int = 1,
    max_collection_items: int = 1000
) -> ValidatorRegistry:
    """
    Resource quota validator preset
    
    Prevents resource exhaustion attacks:
    - File size limits (for read operations)
    - Payload size limits (for write operations)
    - Collection size limits (for batch operations)
    
    v0.1.3+ NEW PRESET
    
    Args:
        max_file_mb: Maximum file size in MB (default: 10MB)
        max_payload_mb: Maximum payload size in MB (default: 1MB)
        max_collection_items: Maximum collection size (default: 1000 items)
    
    Returns:
        ValidatorRegistry: Configured validator registry
    
    Example:
        >>> # Limit file reads to 5MB, writes to 500KB
        >>> session = Session(validator=presets.resource_limited(
        ...     max_file_mb=5,
        ...     max_payload_mb=0.5,
        ...     max_collection_items=500
        ... ))
    """
    from ..core.validate.builtin.resource import (
        max_file_size_precondition,
        max_payload_size_precondition,
        max_collection_size_precondition,
    )
    
    registry = ValidatorRegistry()
    
    # File size limits for read operations
    file_size_checker = max_file_size_precondition(
        path_param="path",
        max_bytes=max_file_mb * 1024 * 1024
    )
    
    read_tools = [
        ("file.read", True),  # (tool, is_prefix)
        ("read_file", False),
    ]
    
    for tool, is_prefix in read_tools:
        registry.register_precondition(tool, file_size_checker, is_prefix=is_prefix)
    
    # Payload size limits for write operations
    payload_size_checker = max_payload_size_precondition(
        param_name="content",
        max_bytes=max_payload_mb * 1024 * 1024
    )
    
    write_tools = [
        ("file.write", True),
        ("write_file", False),
    ]
    
    for tool, is_prefix in write_tools:
        registry.register_precondition(tool, payload_size_checker, is_prefix=is_prefix)
    
    # Collection size limits
    collection_size_checker = max_collection_size_precondition(
        param_name="items",
        max_items=max_collection_items
    )
    
    batch_tools = [
        ("batch", True),
        ("bulk", True),
        ("process_items", False),
    ]
    
    for tool, is_prefix in batch_tools:
        registry.register_precondition(tool, collection_size_checker, is_prefix=is_prefix)
    
    return registry


def combined_safe(
    strict: bool = True,
    sandbox_root: str = None,
    allowed_domains: List[str] = None,
    max_file_mb: int = 10,
    max_payload_mb: int = 1
) -> ValidatorRegistry:
    """
    Combined safety preset (file system + network + resource limits)
    
    Combines all safety presets into one comprehensive configuration:
    - File system safety (with optional strict mode)
    - Network safety (with optional domain whitelist)
    - Resource limits (file size, payload size, collection size)
    
    v0.1.3+ NEW PRESET - Recommended for production use
    
    Args:
        strict: Enable strict security mode (path traversal, SSRF prevention)
        sandbox_root: Sandbox root directory (uses cwd if None)
        allowed_domains: Domain whitelist for HTTP requests
        max_file_mb: Maximum file size in MB
        max_payload_mb: Maximum payload size in MB
    
    Returns:
        ValidatorRegistry: Configured validator registry
    
    Example:
        >>> # Production-ready configuration
        >>> session = Session(validator=presets.combined_safe(
        ...     strict=True,
        ...     sandbox_root="/app/workspace",
        ...     allowed_domains=["api.github.com", "*.openai.com"],
        ...     max_file_mb=5,
        ...     max_payload_mb=1
        ... ))
    """
    registry = ValidatorRegistry()
    
    # Merge all presets
    fs_registry = fs_safe(strict=strict, sandbox_root=sandbox_root)
    net_registry = net_safe(strict=strict, allowed_domains=allowed_domains, block_internal=True)
    resource_registry = resource_limited(
        max_file_mb=max_file_mb,
        max_payload_mb=max_payload_mb,
        max_collection_items=1000
    )
    
    # Merge exact match builtin
    for tool_name, tool_validators in fs_registry._validators.items():
        for validator in tool_validators.pre:
            registry.register_precondition(tool_name, validator, is_prefix=False)
        for validator in tool_validators.post:
            registry.register_postcondition(tool_name, validator, is_prefix=False)
    
    for tool_name, tool_validators in net_registry._validators.items():
        for validator in tool_validators.pre:
            registry.register_precondition(tool_name, validator, is_prefix=False)
        for validator in tool_validators.post:
            registry.register_postcondition(tool_name, validator, is_prefix=False)
    
    for tool_name, tool_validators in resource_registry._validators.items():
        for validator in tool_validators.pre:
            registry.register_precondition(tool_name, validator, is_prefix=False)
        for validator in tool_validators.post:
            registry.register_postcondition(tool_name, validator, is_prefix=False)
    
    # Merge prefix builtin
    for prefix, tool_validators in fs_registry._prefix_validators.items():
        for validator in tool_validators.pre:
            registry.register_precondition(prefix, validator, is_prefix=True)
        for validator in tool_validators.post:
            registry.register_postcondition(prefix, validator, is_prefix=True)
    
    for prefix, tool_validators in net_registry._prefix_validators.items():
        for validator in tool_validators.pre:
            registry.register_precondition(prefix, validator, is_prefix=True)
        for validator in tool_validators.post:
            registry.register_postcondition(prefix, validator, is_prefix=True)
    
    for prefix, tool_validators in resource_registry._prefix_validators.items():
        for validator in tool_validators.pre:
            registry.register_precondition(prefix, validator, is_prefix=True)
        for validator in tool_validators.post:
            registry.register_postcondition(prefix, validator, is_prefix=True)
    
    return registry


__all__ = [
    "fs_safe", 
    "net_safe", 
    "file_path_precondition",
    "fs_safe_sandbox",  # Deprecated, kept for compatibility
    "resource_limited",  # v0.1.3+
    "combined_safe",  # v0.1.3+
]

