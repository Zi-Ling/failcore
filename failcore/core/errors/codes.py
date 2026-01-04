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
SANDBOX_VIOLATION: Final[str] = "SANDBOX_VIOLATION"
PATH_TRAVERSAL: Final[str] = "PATH_TRAVERSAL"
PATH_INVALID: Final[str] = "PATH_INVALID"
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

# tool/runtime (local)
TOOL_NOT_FOUND: Final[str] = "TOOL_NOT_FOUND"
TOOL_EXECUTION_FAILED: Final[str] = "TOOL_EXECUTION_FAILED"
ASYNC_SYNC_MISMATCH: Final[str] = "ASYNC_SYNC_MISMATCH"
TOOL_NAME_CONFLICT: Final[str] = "TOOL_NAME_CONFLICT"

# remote tool errors (MCP/Proxy/Network)
REMOTE_TIMEOUT: Final[str] = "REMOTE_TIMEOUT"
REMOTE_UNREACHABLE: Final[str] = "REMOTE_UNREACHABLE"
REMOTE_PROTOCOL_MISMATCH: Final[str] = "REMOTE_PROTOCOL_MISMATCH"
REMOTE_TOOL_NOT_FOUND: Final[str] = "REMOTE_TOOL_NOT_FOUND"
REMOTE_INVALID_PARAMS: Final[str] = "REMOTE_INVALID_PARAMS"
REMOTE_SERVER_ERROR: Final[str] = "REMOTE_SERVER_ERROR"

# resource limits (P0-2)
RESOURCE_LIMIT_TIMEOUT: Final[str] = "RESOURCE_LIMIT_TIMEOUT"
RESOURCE_LIMIT_OUTPUT: Final[str] = "RESOURCE_LIMIT_OUTPUT"
RESOURCE_LIMIT_EVENTS: Final[str] = "RESOURCE_LIMIT_EVENTS"
RESOURCE_LIMIT_FILE: Final[str] = "RESOURCE_LIMIT_FILE"
RESOURCE_LIMIT_CONCURRENCY: Final[str] = "RESOURCE_LIMIT_CONCURRENCY"

# retry exhausted (P0-3)
RETRY_EXHAUSTED: Final[str] = "RETRY_EXHAUSTED"

# approval/governance (HITL)
APPROVAL_REQUIRED: Final[str] = "APPROVAL_REQUIRED"
APPROVAL_REJECTED: Final[str] = "APPROVAL_REJECTED"
APPROVAL_TIMEOUT: Final[str] = "APPROVAL_TIMEOUT"

# economic/cost guardrails
ECONOMIC_BUDGET_EXCEEDED: Final[str] = "ECONOMIC_BUDGET_EXCEEDED"
ECONOMIC_BURN_RATE_EXCEEDED: Final[str] = "ECONOMIC_BURN_RATE_EXCEEDED"
ECONOMIC_TOKEN_LIMIT: Final[str] = "ECONOMIC_TOKEN_LIMIT"
ECONOMIC_COST_ESTIMATION_FAILED: Final[str] = "ECONOMIC_COST_ESTIMATION_FAILED"
BURN_RATE_EXCEEDED: Final[str] = "BURN_RATE_EXCEEDED"

# data loss prevention (DLP/taint tracking)
DATA_LEAK_PREVENTED: Final[str] = "DATA_LEAK_PREVENTED"
DATA_TAINTED: Final[str] = "DATA_TAINTED"
SANITIZATION_REQUIRED: Final[str] = "SANITIZATION_REQUIRED"

# semantic validation (high-confidence intent guard)
SEMANTIC_VIOLATION: Final[str] = "SEMANTIC_VIOLATION"


# ---- semantic groups (internal helpers) ----

FS_CODES: Final[set[str]] = {
    FILE_NOT_FOUND,
    PERMISSION_DENIED,
    SANDBOX_VIOLATION,
    PATH_TRAVERSAL,
    PATH_INVALID,
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
    ASYNC_SYNC_MISMATCH,
    TOOL_NAME_CONFLICT,
}

# remote tool/transport codes
REMOTE_CODES: Final[set[str]] = {
    REMOTE_TIMEOUT,
    REMOTE_UNREACHABLE,
    REMOTE_PROTOCOL_MISMATCH,
    REMOTE_TOOL_NOT_FOUND,
    REMOTE_INVALID_PARAMS,
    REMOTE_SERVER_ERROR,
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
    SANDBOX_VIOLATION,
    PATH_TRAVERSAL,
    PATH_INVALID,
    ABSOLUTE_PATH,
    UNC_PATH,
    NT_PATH,
    DEVICE_PATH,
    SYMLINK_ESCAPE,
    SSRF_BLOCKED,
    PRIVATE_NETWORK_BLOCKED,
    SEMANTIC_VIOLATION,
}

# Operational error codes (registry, validation, execution, remote, limits, retry)
# These are well-defined operational states that should not be downgraded
OPERATIONAL_CODES: Final[set[str]] = {
    TOOL_NOT_FOUND,
    FILE_NOT_FOUND,
    PERMISSION_DENIED,
    ASYNC_SYNC_MISMATCH,
    TOOL_NAME_CONFLICT,
    # Remote codes
    REMOTE_TIMEOUT,
    REMOTE_UNREACHABLE,
    REMOTE_PROTOCOL_MISMATCH,
    REMOTE_TOOL_NOT_FOUND,
    REMOTE_INVALID_PARAMS,
    REMOTE_SERVER_ERROR,
    # Resource limit codes (P0-2)
    RESOURCE_LIMIT_TIMEOUT,
    RESOURCE_LIMIT_OUTPUT,
    RESOURCE_LIMIT_EVENTS,
    RESOURCE_LIMIT_FILE,
    RESOURCE_LIMIT_CONCURRENCY,
    # Retry codes (P0-3)
    RETRY_EXHAUSTED,
    # Approval codes (HITL)
    APPROVAL_REQUIRED,
    APPROVAL_REJECTED,
    APPROVAL_TIMEOUT,
    # Economic codes
    ECONOMIC_BUDGET_EXCEEDED,
    ECONOMIC_TOKEN_LIMIT,
    ECONOMIC_COST_ESTIMATION_FAILED,
    # DLP codes
    DATA_LEAK_PREVENTED,
    DATA_TAINTED,
    SANITIZATION_REQUIRED,
    # Semantic codes
    SEMANTIC_VIOLATION,
}