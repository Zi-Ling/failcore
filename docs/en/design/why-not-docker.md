# Why Not Docker

FailCore doesn't rely on Docker or containerization, instead using lightweight runtime protection.

---

## Design Philosophy

FailCore's design philosophy is:

- ✅ **Lightweight**: No container runtime required
- ✅ **Fast**: Low overhead, suitable for production
- ✅ **Simple**: Easy to integrate and deploy
- ✅ **Deterministic**: Predictable behavior

---

## Docker Limitations

### 1. Performance Overhead

Docker containers introduce performance overhead:
- Virtualization layer
- Network isolation
- Filesystem mounts

For frequent tool calls in AI agents, this overhead may be unacceptable.

### 2. Deployment Complexity

Docker requires:
- Docker daemon
- Container image management
- Network configuration
- Volume mounts

Increases deployment and maintenance complexity.

### 3. Resource Limits

Docker's resource limits may:
- Limit concurrency
- Affect performance
- Be difficult to tune

### 4. Debugging Difficulties

Containerized environments:
- Isolated logs
- Limited debugging tools
- Difficult to access host resources

---

## FailCore Alternatives

### 1. Sandbox Isolation

FailCore uses **filesystem sandboxing**:

```python
with run(policy="fs_safe", sandbox="./workspace") as ctx:
    # All file operations restricted to sandbox
    pass
```

**Advantages:**
- Lightweight (no virtualization)
- Fast (direct filesystem access)
- Simple (just specify directory)

### 2. Policy Protection

FailCore uses **policy-driven** protection:

```python
with run(policy="net_safe") as ctx:
    # Policy automatically blocks SSRF
    pass
```

**Advantages:**
- Fine-grained control
- Configurable
- Auditable

### 3. Process Isolation (Optional)

For scenarios requiring stronger isolation, FailCore supports process isolation:

```python
from failcore.core.executor.process import ProcessExecutor

executor = ProcessExecutor(
    working_dir="./workspace",
    timeout_s=60
)
```

**Advantages:**
- Optional feature
- Doesn't affect performance (not used by default)
- Provides additional protection layer

---

## When to Use Docker

Although FailCore doesn't rely on Docker, Docker is still useful in the following scenarios:

### 1. Complete Isolation

If you need complete isolation (e.g., running untrusted code), Docker may be more appropriate.

### 2. Environment Consistency

If you need to ensure environment consistency (e.g., CI/CD), Docker may be more appropriate.

### 3. Multi-Tenancy

If you need multi-tenant isolation, Docker may be more appropriate.

---

## FailCore + Docker

FailCore can be used together with Docker:

```dockerfile
FROM python:3.11

# Install FailCore
RUN pip install failcore

# Use FailCore inside container
# FailCore provides additional protection layer
```

**Advantages:**
- Docker provides environment isolation
- FailCore provides execution-time protection
- Double protection

---

## Performance Comparison

### FailCore Sandbox

- Overhead: < 1ms per check
- Startup time: Instant
- Resource usage: Minimal

### Docker Container

- Overhead: 10-100ms per call
- Startup time: 1-5 seconds
- Resource usage: Moderate

---

## Summary

FailCore chooses not to use Docker because:

- ✅ Performance: Lower overhead
- ✅ Simplicity: Easier to integrate
- ✅ Flexibility: Configurable protection
- ✅ Speed: Instant startup

For most AI agent scenarios, FailCore's lightweight protection is sufficient.

---

## Next Steps

- [Why Not Only Prompt](why-not-only-prompt.md) - Learn about FailCore's design philosophy
- [Design Philosophy](philosophy.md) - Deep dive into FailCore's design
