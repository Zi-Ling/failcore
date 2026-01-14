# Execution Boundary

Execution Boundary is a core concept of FailCore that defines the allowed scope of operations.

---

## What is an Execution Boundary

An execution boundary is a **declarative specification** that defines the allowed side-effect categories and types during a run.

It's like an "allowlist":
- Defines which operations are allowed
- All other operations are forbidden
- Statically defined before execution, immutable at runtime

---

## Boundary Types

### Side-Effect Categories

FailCore recognizes the following side-effect categories:

- **FILESYSTEM**: Filesystem operations
  - Read files
  - Write files
  - Delete files
  - Create directories

- **NETWORK**: Network operations
  - Outbound HTTP/HTTPS requests
  - DNS queries
  - Socket connections

- **PROCESS**: Process operations
  - Spawn processes
  - Terminate processes
  - Send signals

### Side-Effect Types

Each category has specific types:

```python
# Filesystem types
FILESYSTEM_READ = "filesystem.read"
FILESYSTEM_WRITE = "filesystem.write"
FILESYSTEM_DELETE = "filesystem.delete"

# Network types
NETWORK_EGRESS = "network.egress"
NETWORK_DNS = "network.dns"

# Process types
PROCESS_SPAWN = "process.spawn"
PROCESS_KILL = "process.kill"
```

---

## Boundary Definition

### Using Preset Boundaries

FailCore provides preset boundaries:

```python
from failcore import run

# Only allow filesystem operations
with run(policy="fs_safe") as ctx:
    # Allow file read/write
    # Block network and process operations
    pass

# Only allow network operations
with run(policy="net_safe") as ctx:
    # Allow network requests
    # Block filesystem and process operations
    pass

# Allow all safe operations
with run(policy="safe") as ctx:
    # Allow filesystem and network operations
    # Block process operations
    pass
```

### Custom Boundaries

You can also create custom boundaries:

```python
from failcore.core.config.boundaries import get_boundary

# Create read-only filesystem boundary
boundary = get_boundary(
    allowed_categories=["FILESYSTEM"],
    allowed_types=["filesystem.read"],  # Only allow reads
    blocked_types=["filesystem.write", "filesystem.delete"]
)
```

---

## Boundary Check Flow

When a tool call occurs:

```
1. Predict side effects
   ↓
2. Check if side-effect type is in allowlist
   ↓
3. If yes → Allow execution
4. If no → Block execution
```

### Example

```python
from failcore import run, guard

# Define read-only boundary
with run(policy="fs_safe") as ctx:
    @guard()
    def read_file(path: str):
        with open(path, "r") as f:
            return f.read()
    
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # This will succeed (read is within boundary)
    read_file("data.txt")
    
    # This will be blocked (write is not within boundary)
    try:
        write_file("output.txt", "data")
    except PolicyDeny:
        print("Write blocked by boundary")
```

---

## Boundary vs Policy

**Boundary**:
- Declarative: Defines what's allowed
- Static: Defined before execution
- Simple: Yes/No judgment

**Policy**:
- Procedural: Defines how to check
- Dynamic: Can be context-based
- Complex: Can contain conditional logic

Boundaries are **fast pre-checks**, policies are **detailed validation**.

---

## Boundary Violations

When an operation exceeds the boundary:

1. **Detection**: FailCore detects side-effect type is not in allowlist
2. **Blocking**: Execution is immediately blocked, tool function doesn't run
3. **Recording**: Violation recorded to trace file
4. **Exception**: Raises `SideEffectBoundaryCrossedError`

### Violation Record

Violation records in trace file:

```json
{
  "event": "POLICY_DENIED",
  "reason": "Side-effect boundary crossed",
  "side_effect_type": "filesystem.write",
  "allowed_categories": ["FILESYSTEM"],
  "allowed_types": ["filesystem.read"],
  "blocked_type": "filesystem.write"
}
```

---

## Boundary Configuration

### In run()

```python
from failcore import run

with run(
    policy="fs_safe",
    # Boundary implicitly defined through policy
) as ctx:
    pass
```

### Explicit Boundary

```python
from failcore.core.config.boundaries import get_boundary
from failcore.core.executor.executor import Executor

boundary = get_boundary("strict")  # or "permissive", "readonly"

executor = Executor(
    side_effect_boundary=boundary,
    # ...
)
```

---

## Boundary Presets

FailCore provides the following boundary presets:

### strict

Most restrictive boundary:
- Only allows explicitly declared side effects
- All other operations blocked

### permissive

Permissive boundary:
- Allows most common operations
- Only blocks obviously dangerous operations

### readonly

Read-only boundary:
- Only allows read operations
- Blocks all write operations

---

## Best Practices

### 1. Principle of Least Privilege

Only allow necessary side effects:

```python
# Good: Only allow needed operations
with run(policy="fs_safe") as ctx:  # Only filesystem
    pass

# Bad: Allow all operations
with run(policy=None) as ctx:  # No boundary
    pass
```

### 2. Explicit Boundaries

Use explicit boundary definitions:

```python
# Good: Explicitly specify allowed operations
boundary = get_boundary(
    allowed_types=["filesystem.read", "filesystem.write"]
)

# Bad: Use overly broad boundaries
boundary = get_boundary("permissive")  # May allow too much
```

### 3. Test Boundaries

Verify boundaries work as expected:

```python
def test_boundary():
    with run(policy="fs_safe") as ctx:
        # Should succeed
        read_file("data.txt")
        
        # Should be blocked
        try:
            write_file("/etc/passwd", "hack")
            assert False, "Should be blocked"
        except PolicyDeny:
            pass  # Expected behavior
```

---

## Summary

Execution boundaries are FailCore's first line of defense:

- ✅ Declarative definition of allowed operations
- ✅ Fast pre-check, before policy checks
- ✅ Simple and effective, easy to understand
- ✅ Clear violation reports

Boundary + Policy = Multi-layer security protection.

---

## Next Steps

- [Side Effects](../concepts/side-effects.md) - Learn how side effects are detected and recorded
- [Policy](../concepts/policy.md) - Deep dive into policy system
- [Filesystem Safety](../guides/fs-safety.md) - Filesystem boundary practices
