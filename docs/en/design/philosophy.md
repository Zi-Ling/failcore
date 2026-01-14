# Design Philosophy

This document explains FailCore's core design principles.

---

## Core Principles

### 1. Execution-Time Protection

FailCore focuses on **execution-time** protection, not generation time.

**Why:**
- Generation-time values may look correct
- Execution-time values may still be wrong
- Only execution time can determine actual behavior

**Example:**
```python
# Generation time: Path looks correct
path = "data/file.txt"

# Execution time: Actual value may be wrong
path = "/etc/passwd"  # Blocked
```

### 2. Deterministic Guarantees

FailCore provides **deterministic** guarantees, not probabilistic.

**Why:**
- Security needs determinism
- Probabilistic guarantees are unreliable
- Deterministic guarantees are testable

**Example:**
```python
# Deterministic: Always blocks
with run(policy="fs_safe") as ctx:
    write_file("/etc/passwd", "hack")  # Always blocked
```

### 3. Least Privilege

FailCore follows the **least privilege** principle.

**Why:**
- Reduces attack surface
- Lowers risk
- Improves security

**Example:**
```python
# Only allow filesystem reads
with run(policy="fs_safe") as ctx:
    # Only allow reads, don't allow writes
    read_file("data.txt")  # Allowed
    write_file("output.txt", "data")  # Blocked
```

### 4. Auditability

FailCore records all execution, providing **auditability**.

**Why:**
- Post-analysis
- Compliance requirements
- Debugging support

**Example:**
```python
with run(policy="fs_safe") as ctx:
    write_file("test.txt", "Hello")
    
# Trace file contains complete records
# - Tool calls
# - Policy decisions
# - Execution results
```

---

## Design Choices

### 1. Lightweight vs Heavyweight

FailCore chooses **lightweight**:

- ✅ No virtualization
- ✅ Low overhead
- ✅ Fast startup

**Reason:**
- AI agents need frequent calls
- Performance is critical
- Simple to integrate

### 2. Policy-Driven vs Hardcoded

FailCore chooses **policy-driven**:

- ✅ Configurable
- ✅ Extensible
- ✅ Testable

**Reason:**
- Different scenarios need different rules
- Rules may change
- Need flexibility

### 3. Declarative vs Procedural

FailCore chooses **declarative** boundaries + **procedural** policies:

- ✅ Boundaries: Declarative (simple)
- ✅ Policies: Procedural (flexible)

**Reason:**
- Boundaries need to be simple and clear
- Policies need complex logic
- Balance simplicity and flexibility

---

## Architecture Principles

### 1. Single Responsibility

Each component has a single responsibility:

- **Executor**: Execute tools
- **Policy**: Check policies
- **Recorder**: Record traces
- **Guardian**: Cost control

**Advantages:**
- Easy to understand
- Easy to test
- Easy to maintain

### 2. Composability

Components can be composed:

```python
executor = Executor(
    policy=policy,
    recorder=recorder,
    cost_guardian=guardian
)
```

**Advantages:**
- Flexibility
- Extensibility
- Testability

### 3. Observability

All operations are observable:

- Trace files
- Logs
- Metrics

**Advantages:**
- Debuggable
- Auditable
- Analyzable

---

## Security Model

### 1. Default Deny

FailCore defaults to **deny**, unless explicitly allowed:

```python
# Default: Deny all operations
with run(policy="safe") as ctx:
    # Only operations allowed by policy can execute
    pass
```

### 2. Least Privilege

Only grant **minimum necessary** permissions:

```python
# Only allow filesystem reads
with run(policy="fs_safe") as ctx:
    # Writes blocked
    pass
```

### 3. Defense in Depth

Multiple layers of protection:

- Boundary checks
- Policy checks
- Cost control

**Advantages:**
- Even if one layer fails, other layers still protect
- Provides redundant protection

---

## Performance Considerations

### 1. Low Overhead

FailCore's overhead is minimal:

- Policy checks: < 1ms
- Trace recording: Asynchronous
- Side-effect detection: Static analysis

**Reason:**
- AI agents need frequent calls
- Performance is critical

### 2. Fail Fast

FailCore **fails fast**:

- Policy checks before execution
- Violations immediately blocked
- Don't execute dangerous operations

**Advantages:**
- Reduce resource waste
- Fast feedback
- Lower risk

---

## Extensibility

### 1. Plugin System

FailCore supports plugins:

- Custom validators
- Custom policies
- Custom middleware

**Advantages:**
- Extensible
- Customizable
- Integrable

### 2. API Design

FailCore provides clear APIs:

```python
# Simple API
with run(policy="fs_safe") as ctx:
    @guard()
    def write_file(path: str, content: str):
        pass
```

**Advantages:**
- Easy to use
- Easy to understand
- Easy to integrate

---

## Summary

FailCore's design philosophy:

- ✅ **Execution-time protection**: Check at execution time, not generation time
- ✅ **Deterministic guarantees**: Provide predictable behavior
- ✅ **Least privilege**: Only grant necessary permissions
- ✅ **Auditability**: Record all execution
- ✅ **Lightweight**: Low overhead, fast startup
- ✅ **Extensible**: Support plugins and customization

These principles guide FailCore's development and evolution.

---

## Next Steps

- [Why Not Docker](why-not-docker.md) - Learn about design choices
- [Why Not Only Prompt](why-not-only-prompt.md) - Learn about design philosophy
- [Core Concepts](../concepts/execution-boundary.md) - Deep dive into implementation
