# Error Codes

Complete reference for FailCore error codes.

---

## Overview

FailCore uses standardized error codes to categorize failures. All errors are instances of `FailCoreError` with an `error_code` field.

---

## Error Code Categories

### Generic Errors

| Code | Description |
|------|-------------|
| `UNKNOWN` | Unknown or unclassified error |
| `INTERNAL_ERROR` | Internal FailCore error |
| `INVALID_ARGUMENT` | Invalid function argument |
| `PRECONDITION_FAILED` | Precondition not met |
| `NOT_IMPLEMENTED` | Feature not implemented |
| `TIMEOUT` | Operation timed out |

---

### Security & Validation Errors

| Code | Description |
|------|-------------|
| `POLICY_DENIED` | Policy denied execution |
| `SANDBOX_VIOLATION` | Path outside sandbox boundary |
| `PATH_TRAVERSAL` | Path traversal detected (`../` escape) |
| `PATH_INVALID` | Invalid path format |
| `ABSOLUTE_PATH` | Absolute path not allowed |
| `UNC_PATH` | UNC path not allowed (Windows) |
| `NT_PATH` | NT path not allowed (Windows) |
| `DEVICE_PATH` | Device path not allowed (Windows) |
| `SYMLINK_ESCAPE` | Symlink escape detected |

---

### Filesystem Errors

| Code | Description |
|------|-------------|
| `FILE_NOT_FOUND` | File does not exist |
| `PERMISSION_DENIED` | Permission denied |

---

### Network Errors

| Code | Description |
|------|-------------|
| `SSRF_BLOCKED` | SSRF attack blocked |
| `PRIVATE_NETWORK_BLOCKED` | Private network access blocked |

---

### Tool & Runtime Errors

| Code | Description |
|------|-------------|
| `TOOL_NOT_FOUND` | Tool not registered |
| `TOOL_EXECUTION_FAILED` | Tool execution failed |
| `ASYNC_SYNC_MISMATCH` | Async/sync mismatch |
| `TOOL_NAME_CONFLICT` | Tool name conflict |

---

### Remote Tool Errors

| Code | Description |
|------|-------------|
| `REMOTE_TIMEOUT` | Remote tool timeout |
| `REMOTE_UNREACHABLE` | Remote tool unreachable |
| `REMOTE_PROTOCOL_MISMATCH` | Protocol mismatch |
| `REMOTE_TOOL_NOT_FOUND` | Remote tool not found |
| `REMOTE_INVALID_PARAMS` | Invalid remote tool parameters |
| `REMOTE_SERVER_ERROR` | Remote server error |

---

### Resource Limit Errors

| Code | Description |
|------|-------------|
| `RESOURCE_LIMIT_TIMEOUT` | Timeout limit exceeded |
| `RESOURCE_LIMIT_OUTPUT` | Output size limit exceeded |
| `RESOURCE_LIMIT_EVENTS` | Event count limit exceeded |
| `RESOURCE_LIMIT_FILE` | File size limit exceeded |
| `RESOURCE_LIMIT_CONCURRENCY` | Concurrency limit exceeded |

---

### Retry Errors

| Code | Description |
|------|-------------|
| `RETRY_EXHAUSTED` | All retry attempts exhausted |

---

### Approval Errors (HITL)

| Code | Description |
|------|-------------|
| `APPROVAL_REQUIRED` | Human approval required |
| `APPROVAL_REJECTED` | Approval rejected |
| `APPROVAL_TIMEOUT` | Approval timeout |

---

### Economic/Cost Errors

| Code | Description |
|------|-------------|
| `ECONOMIC_BUDGET_EXCEEDED` | Budget limit exceeded |
| `ECONOMIC_BURN_RATE_EXCEEDED` | Burn rate limit exceeded |
| `ECONOMIC_TOKEN_LIMIT` | Token limit exceeded |
| `ECONOMIC_COST_ESTIMATION_FAILED` | Cost estimation failed |
| `BURN_RATE_EXCEEDED` | Burn rate exceeded (alias) |

---

### Data Loss Prevention (DLP)

| Code | Description |
|------|-------------|
| `DATA_LEAK_PREVENTED` | Data leak prevented |
| `DATA_TAINTED` | Data is tainted |
| `SANITIZATION_REQUIRED` | Sanitization required |

---

### Semantic Validation

| Code | Description |
|------|-------------|
| `SEMANTIC_VIOLATION` | Semantic validation violation |

---

## Error Code Groups

FailCore organizes error codes into semantic groups:

### Security Codes

These codes indicate security violations and must be handled explicitly:

```python
from failcore.core.errors import codes

if error.error_code in codes.SECURITY_CODES:
    # Security violation - handle explicitly
    log_security_event(error)
```

**Security codes:**
- `POLICY_DENIED`
- `SANDBOX_VIOLATION`
- `PATH_TRAVERSAL`
- `PATH_INVALID`
- `ABSOLUTE_PATH`
- `UNC_PATH`
- `NT_PATH`
- `DEVICE_PATH`
- `SYMLINK_ESCAPE`
- `SSRF_BLOCKED`
- `PRIVATE_NETWORK_BLOCKED`
- `SEMANTIC_VIOLATION`

### Operational Codes

Well-defined operational states that should not be downgraded:

```python
if error.error_code in codes.OPERATIONAL_CODES:
    # Operational error - handle appropriately
    handle_operational_error(error)
```

**Operational codes include:**
- Tool errors (`TOOL_NOT_FOUND`, `TOOL_EXECUTION_FAILED`, etc.)
- Remote errors (`REMOTE_TIMEOUT`, `REMOTE_UNREACHABLE`, etc.)
- Resource limits (`RESOURCE_LIMIT_*`)
- Retry errors (`RETRY_EXHAUSTED`)
- Approval errors (`APPROVAL_*`)
- Economic errors (`ECONOMIC_*`)
- DLP errors (`DATA_*`)

### Fallback Codes

Non-security, non-decisive fallback categories:

```python
if error.error_code in codes.DEFAULT_FALLBACK_CODES:
    # Fallback error - may be downgraded
    handle_fallback_error(error)
```

**Fallback codes:**
- `UNKNOWN`
- `INTERNAL_ERROR`
- `INVALID_ARGUMENT`
- `PRECONDITION_FAILED`
- `TOOL_EXECUTION_FAILED`

---

## Using Error Codes

### Checking Error Codes

```python
from failcore import run, guard
from failcore.core.errors import FailCoreError, codes

try:
    with run(policy="fs_safe") as ctx:
        @guard()
        def write_file(path: str, content: str):
            with open(path, "w") as f:
                f.write(content)
        
        write_file("/etc/passwd", "hack")
except FailCoreError as e:
    if e.error_code == codes.PATH_TRAVERSAL:
        print("Path traversal detected")
    elif e.error_code == codes.SANDBOX_VIOLATION:
        print("Sandbox violation")
    elif e.error_code in codes.SECURITY_CODES:
        print("Security violation:", e.error_code)
```

### Error Code Properties

```python
error = FailCoreError(
    message="Path traversal detected",
    error_code=codes.PATH_TRAVERSAL
)

# Check if security error
if error.is_security:
    print("Security violation")

# Get error details
details = error.to_dict()
print(details["error_code"])  # "PATH_TRAVERSAL"
```

### LLM-Friendly Error Messages

FailCore errors include LLM-friendly fields:

```python
error = FailCoreError(
    message="Path traversal detected",
    error_code=codes.PATH_TRAVERSAL,
    suggestion="Use relative paths, don't use '..'",
    hint="The path contains '..' which attempts to escape the sandbox",
    remediation={
        "template": "Use path: {safe_path}",
        "vars": {"safe_path": "./data/file.txt"}
    }
)

print(error)
# [PATH_TRAVERSAL] Path traversal detected
#
# [Suggestion] Use relative paths, don't use '..'
# [Hint] The path contains '..' which attempts to escape the sandbox
# [Remediation] Use path: {safe_path} (vars: {'safe_path': './data/file.txt'})
```

---

## Error Code Normalization

Unknown error codes from upstream systems are normalized to prevent taxonomy explosion:

```python
from failcore.core.errors.exceptions import _normalize_error_code

# Unknown codes are normalized
code = _normalize_error_code("CUSTOM_UPSTREAM_ERROR")
# Returns: "UNKNOWN"

# Known security codes are preserved
code = _normalize_error_code("PATH_TRAVERSAL")
# Returns: "PATH_TRAVERSAL"
```

**Normalization rules:**
1. Security codes are preserved as-is
2. Operational codes are preserved as-is
3. Fallback codes are preserved as-is
4. Unknown codes are downgraded to `UNKNOWN`

---

## Next Steps

- [Configuration Reference](configuration.md) - Configuration options
- [Troubleshooting](../operations/troubleshooting.md) - Common error scenarios
