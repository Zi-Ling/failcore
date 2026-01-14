# Filesystem Safety

This guide explains how to use FailCore to protect filesystem operations.

---

## Overview

The filesystem safety policy (`fs_safe`) provides:

- ✅ Sandbox path protection
- ✅ Path traversal prevention
- ✅ File size limits
- ✅ Absolute path blocking

---

## Basic Usage

### Enable Filesystem Safety

```python
from failcore import run, guard

with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # This will succeed (within sandbox)
    write_file("test.txt", "Hello")
    
    # This will be blocked (path traversal)
    try:
        write_file("../../etc/passwd", "hack")
    except PolicyDeny:
        print("Path traversal blocked")
```

---

## Sandbox Configuration

### Default Sandbox

If `sandbox` is not specified, FailCore uses the default sandbox:

```
<project root>/.failcore/sandbox/
```

### Custom Sandbox

```python
# Relative path
with run(policy="fs_safe", sandbox="./workspace") as ctx:
    pass

# Absolute path (requires allow_outside_root=True)
with run(
    policy="fs_safe",
    sandbox="/tmp/my_sandbox",
    allow_outside_root=True,
    allowed_sandbox_roots=[Path("/tmp")]
) as ctx:
    pass
```

### Sandbox Rules

1. **All file operations must be within sandbox**
   - Reads, writes, deletes are restricted
   - Paths must resolve to within sandbox directory

2. **Path traversal is blocked**
   - `../` sequences are detected and blocked
   - Even if final path is within sandbox, path traversal is blocked

3. **Absolute paths are blocked**
   - By default, absolute paths are blocked
   - Unless external paths are explicitly allowed

---

## Path Validation

### Allowed Paths

```python
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def read_file(path: str):
        with open(path, "r") as f:
            return f.read()
    
    # ✅ Relative paths (within sandbox)
    read_file("test.txt")
    read_file("subdir/file.txt")
    
    # ✅ Relative paths (resolve to within sandbox)
    read_file("data/test.txt")  # If sandbox="./data"
```

### Blocked Paths

```python
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # ❌ Path traversal
    try:
        write_file("../../etc/passwd", "hack")
    except PolicyDeny as e:
        print(f"Blocked: {e.result.reason}")
        # Output: Blocked: Path traversal detected: '../../etc/passwd'
    
    # ❌ Absolute path
    try:
        write_file("/etc/passwd", "hack")
    except PolicyDeny as e:
        print(f"Blocked: {e.result.reason}")
        # Output: Blocked: Absolute path not allowed: '/etc/passwd'
    
    # ❌ Outside sandbox
    try:
        write_file("../outside.txt", "data")
    except PolicyDeny as e:
        print(f"Blocked: {e.result.reason}")
        # Output: Blocked: Path would be created outside sandbox: '../outside.txt'
```

---

## File Size Limits

The `fs_safe` policy includes file size limits:

```python
# Default limit: 50MB
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # Small file: succeeds
    write_file("small.txt", "Hello")
    
    # Large file: may be warned or blocked (depending on config)
    large_content = "x" * (100 * 1024 * 1024)  # 100MB
    try:
        write_file("large.txt", large_content)
    except PolicyDeny:
        print("File too large")
```

### Custom File Size Limits

```python
from failcore.core.validate.templates import fs_safe_policy
from failcore.core.validate.contracts import EnforcementMode

# Create custom policy
policy = fs_safe_policy(sandbox_root="./data")
policy.validators["resource_file_size"].config["max_bytes"] = 10 * 1024 * 1024  # 10MB
policy.validators["resource_file_size"].enforcement = EnforcementMode.BLOCK
```

---

## Path Parameter Names

FailCore automatically detects paths in the following parameter names:

- `path`
- `file_path`
- `filename`
- `file`
- `output_path`
- `dst`
- `destination`
- `source`
- `src`

### Custom Path Parameters

If your tool uses different parameter names, configure in policy:

```yaml
validators:
  security_path_traversal:
    config:
      path_params: ["custom_path_param", "another_param"]
```

---

## Error Messages

FailCore provides LLM-friendly error messages:

```python
try:
    write_file("../../etc/passwd", "hack")
except PolicyDeny as e:
    print(e.result.reason)
    # Output: Path traversal detected: '../../etc/passwd'
    
    print(e.result.suggestion)
    # Output: Use relative paths, don't use '..' - Example: 'data/file.txt' instead of '../../etc/passwd'
    
    print(e.result.remediation)
    # Output: {'action': 'sanitize_path', 'template': "Remove '..': {sanitized_path}", 'vars': {'sanitized_path': 'etc/passwd'}}
```

---

## Best Practices

### 1. Always Specify Sandbox

```python
# Good: Explicitly specify sandbox
with run(policy="fs_safe", sandbox="./workspace") as ctx:
    pass

# Bad: Use default sandbox (may be unclear)
with run(policy="fs_safe") as ctx:
    pass
```

### 2. Use Relative Paths

```python
# Good: Relative paths
write_file("data/output.txt", "content")

# Bad: Absolute paths
write_file("/absolute/path/file.txt", "content")
```

### 3. Test Path Validation

```python
def test_path_validation():
    with run(policy="fs_safe", sandbox="./test") as ctx:
        @guard()
        def write_file(path: str, content: str):
            with open(path, "w") as f:
                f.write(content)
        
        # Should succeed
        write_file("test.txt", "data")
        
        # Should be blocked
        try:
            write_file("../../etc/passwd", "hack")
            assert False, "Should be blocked"
        except PolicyDeny:
            pass  # Expected behavior
```

### 4. Monitor Trace Files

```python
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    write_file("test.txt", "Hello")
    
    # View trace file
    print(f"Trace file: {ctx.trace_path}")
    # Run: failcore show {ctx.trace_path}
```

---

## Advanced Configuration

### Allow External Paths

```python
from pathlib import Path

with run(
    policy="fs_safe",
    sandbox="/tmp/external",
    allow_outside_root=True,
    allowed_sandbox_roots=[Path("/tmp")]
) as ctx:
    # Can now use paths under /tmp
    pass
```

### Custom Policy

```python
from failcore.core.validate.templates import fs_safe_policy
from failcore.core.validate.contracts import EnforcementMode

# Create custom filesystem policy
policy = fs_safe_policy(sandbox_root="./data")

# Modify validator configuration
policy.validators["security_path_traversal"].config["sandbox_root"] = "./custom_sandbox"
policy.validators["resource_file_size"].config["max_bytes"] = 10 * 1024 * 1024  # 10MB
policy.validators["resource_file_size"].enforcement = EnforcementMode.BLOCK

# Use custom policy
# Note: Currently need to use through Executor directly, run() API only supports preset names
```

---

## Common Questions

### Q: Why are relative paths also blocked?

A: If relative paths resolve outside the sandbox, they are blocked. Ensure all paths are within the sandbox.

### Q: How to allow specific external paths?

A: Use `allow_outside_root=True` and `allowed_sandbox_roots` parameters.

### Q: Can file size limits be disabled?

A: Yes, set `resource_file_size` validator's `enforcement` to `SHADOW` or disable the validator.

---

## Summary

The filesystem safety policy provides:

- ✅ Sandbox isolation
- ✅ Path traversal protection
- ✅ File size limits
- ✅ LLM-friendly error messages

---

## Next Steps

- [Network Control](network-control.md) - Learn about network security protection
- [Policy](../concepts/policy.md) - Deep dive into policy system
- [Execution Boundary](../concepts/execution-boundary.md) - Learn how boundaries work
