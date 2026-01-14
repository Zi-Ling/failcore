# Why Not Only Prompt

FailCore doesn't rely on prompt engineering, instead providing execution-time safety guarantees.

---

## Problem: Prompt Limitations

### 1. Prompts Cannot Enforce

Prompts are only **suggestions**, not **guarantees**:

```python
# Prompt might say:
"Only use relative paths, don't use absolute paths"

# But model may still generate:
write_file("/etc/passwd", "hack")
```

**Problem:**
- Models may ignore prompts
- Prompts may be misunderstood
- Prompts cannot enforce

### 2. Prompts Cannot Detect Execution-Time Errors

Even if prompts are correct, execution-time values may still be wrong:

```python
# Prompt: Delete temporary file
# Model generates: delete_file("temp.txt")
# Actually executes: delete_file("/project")  # Wrong path
```

**Problem:**
- Prompts cannot detect execution-time values
- Errors only discovered at execution time
- Too late

### 3. Prompts Cannot Provide Auditing

Prompts cannot provide:
- Execution records
- Policy decisions
- Violation tracking

**Problem:**
- Cannot analyze after the fact
- Cannot audit
- Cannot debug

---

## FailCore Solution

### 1. Execution-Time Enforcement

FailCore checks at **execution time**, not relying on prompts:

```python
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # Even if model generates wrong path, it will be blocked
    write_file("/etc/passwd", "hack")  # Blocked
```

**Advantages:**
- Enforced
- Cannot bypass
- Deterministic guarantees

### 2. Policy-Driven

FailCore uses **policies** instead of prompts:

```python
# Policy defines rules
policy = fs_safe_policy(sandbox_root="./data")

# Policy automatically enforces
with run(policy=policy) as ctx:
    pass
```

**Advantages:**
- Configurable
- Testable
- Auditable

### 3. Complete Tracing

FailCore records all execution:

```python
with run(policy="fs_safe") as ctx:
    write_file("test.txt", "Hello")
    
# Trace file contains:
# - All tool calls
# - Policy decisions
# - Execution results
```

**Advantages:**
- Complete records
- Auditable
- Debuggable

---

## Prompt vs FailCore

### Prompt Approach

```python
# State rules in prompt
prompt = """
Rules:
1. Only use relative paths
2. Don't access /etc
3. Don't access private IPs
"""

# Rely on model to follow rules
result = llm.call(prompt)
```

**Problems:**
- Cannot enforce
- Cannot detect violations
- Cannot provide guarantees

### FailCore Approach

```python
# Policy defines rules
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # Automatically enforced
    write_file("/etc/passwd", "hack")  # Blocked
```

**Advantages:**
- Enforced
- Automatically detected
- Provides guarantees

---

## Prompt + FailCore

Prompts and FailCore can **complement** each other:

```python
# Prompt: Guide model behavior
prompt = """
Use relative paths, e.g., 'data/file.txt'
"""

# FailCore: Enforce
with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # Prompt helps model generate correct paths
    # FailCore ensures even wrong paths are blocked
    result = llm.call(prompt)
    write_file(result.path, result.content)
```

**Advantages:**
- Prompt: Improves correctness rate
- FailCore: Provides last line of defense

---

## Real-World Cases

### Case 1: Path Traversal

**Prompt Approach:**
```python
prompt = "Don't use .. paths"
# Model may still generate: ../../etc/passwd
```

**FailCore Approach:**
```python
with run(policy="fs_safe") as ctx:
    write_file("../../etc/passwd", "hack")  # Automatically blocked
```

### Case 2: SSRF

**Prompt Approach:**
```python
prompt = "Don't access private IPs"
# Model may still generate: http://169.254.169.254
```

**FailCore Approach:**
```python
with run(policy="net_safe") as ctx:
    fetch_url("http://169.254.169.254")  # Automatically blocked
```

---

## Summary

FailCore doesn't rely on prompts because:

- ✅ **Enforcement**: Policies automatically enforce, cannot bypass
- ✅ **Execution-time checks**: Check values at execution time, not generation time
- ✅ **Complete tracing**: Record all execution, auditable
- ✅ **Deterministic guarantees**: Provide predictable behavior

**Prompt + FailCore = Best Practice**

- Prompt: Improves correctness rate
- FailCore: Provides safety guarantees

---

## Next Steps

- [Why Not Docker](why-not-docker.md) - Learn about FailCore's design choices
- [Design Philosophy](philosophy.md) - Deep dive into FailCore's design
