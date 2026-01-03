# failcore/errors/codes.py
from __future__ import annotations

from typing import Final


# ---- canonical error codes (stable public contract) ----
# generic
UNKNOWN: Final[str] = "UNKNOWN"
INTERNAL_ERROR: Final[str] = "INTERNAL_ERROR"
INVALID_ARGUMENT: Final[str] = "INVALID_ARGUMENT"
PRECONDITION_FAILED: Final[str] = "PRECONDITION_FAILED"
NOT_IMPLEMENTED: Final[str] = "NOT_IMPLEMENTED"
TIMEOUT: Final[str] = "TIMEOUT"

# validation / security
POLICY_DENIED: Final[str] = "POLICY_DENIED"
PATH_TRAVERSAL: Final[str] = "PATH_TRAVERSAL"
ABSOLUTE_PATH: Final[str] = "ABSOLUTE_PATH"
UNC_PATH: Final[str] = "UNC_PATH"
NT_PATH: Final[str] = "NT_PATH"
DEVICE_PATH: Final[str] = "DEVICE_PATH"
SYMLINK_ESCAPE: Final[str] = "SYMLINK_ESCAPE"

# fs
FILE_NOT_FOUND: Final[str] = "FILE_NOT_FOUND"
PERMISSION_DENIED: Final[str] = "PERMISSION_DENIED"

# network
SSRF_BLOCKED: Final[str] = "SSRF_BLOCKED"
PRIVATE_NETWORK_BLOCKED: Final[str] = "PRIVATE_NETWORK_BLOCKED"

# tool/runtime
TOOL_NOT_FOUND: Final[str] = "TOOL_NOT_FOUND"
TOOL_EXECUTION_FAILED: Final[str] = "TOOL_EXECUTION_FAILED"


# ---- semantic groups (internal helpers) ----

FS_CODES: Final[set[str]] = {
    FILE_NOT_FOUND,
    PERMISSION_DENIED,
    PATH_TRAVERSAL,
    ABSOLUTE_PATH,
    UNC_PATH,
    NT_PATH,
    DEVICE_PATH,
    SYMLINK_ESCAPE,
}

NETWORK_CODES: Final[set[str]] = {
    SSRF_BLOCKED,
    PRIVATE_NETWORK_BLOCKED,
}

# tool/runtime
TOOL_CODES: Final[set[str]] = {
    TOOL_NOT_FOUND,
    TOOL_EXECUTION_FAILED,
}


# A small set of "default" codes you can use when mapping unknown upstream errors.
# These are NON-security, non-decisive fallback categories.
DEFAULT_FALLBACK_CODES: Final[set[str]] = {
    UNKNOWN,
    INTERNAL_ERROR,
    INVALID_ARGUMENT,
    PRECONDITION_FAILED,
    TOOL_EXECUTION_FAILED,
}

# Explicit security / policy violations.
# These MUST be handled explicitly and never be silently downgraded.
SECURITY_CODES: Final[set[str]] = {
    POLICY_DENIED,
    PATH_TRAVERSAL,
    ABSOLUTE_PATH,
    UNC_PATH,
    NT_PATH,
    DEVICE_PATH,
    SYMLINK_ESCAPE,
    SSRF_BLOCKED,
    PRIVATE_NETWORK_BLOCKED,
}