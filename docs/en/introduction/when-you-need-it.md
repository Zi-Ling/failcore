# When You Need FailCore

FailCore is designed for scenarios that require **execution-time safety guarantees**.

---

## Use Cases

### 1. AI Agents with Real-World Side Effects

When your agent can:
- Modify the filesystem
- Send network requests
- Execute system commands
- Call external APIs

FailCore provides the last line of defense, ensuring these operations don't cause unintended damage.

### 2. Long-Running or Autonomous Workflows

For unattended agent systems:
- Automated tasks
- Continuous monitoring
- Background processing

FailCore can:
- Prevent resource exhaustion
- Stop cost overruns
- Record all operations for audit

### 3. Tools That Touch Sensitive Resources

When tools may access:
- Production databases
- Internal services
- User data
- System configuration

FailCore enforces access control policies.

### 4. Environments Requiring Explainability and Auditability

In scenarios requiring:
- Compliance audits
- Incident investigation
- Accountability tracing

FailCore provides complete execution traces.

---

## Typical Use Cases

### Use Case 1: File Operations Agent

```python
from failcore import run, guard

with run(policy="fs_safe", sandbox="./workspace") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
    
    # This will succeed
    write_file("data/output.txt", "Hello")
    
    # This will be blocked (path traversal)
    write_file("../../etc/passwd", "hack")
```

**Why FailCore is needed:**
- Agents may generate incorrect paths
- Path traversal attacks can damage systems
- FailCore validates paths before writing

### Use Case 2: Network Request Agent

```python
from failcore import run, guard

with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str):
        import urllib.request
        with urllib.request.urlopen(url) as response:
            return response.read()
    
    # This will succeed
    fetch_url("https://api.example.com/data")
    
    # This will be blocked (SSRF)
    fetch_url("http://169.254.169.254/latest/meta-data/")
```

**Why FailCore is needed:**
- SSRF attacks may access internal services
- Agents may be tricked into accessing private IPs
- FailCore blocks private network access

### Use Case 3: Cost Control

```python
from failcore import run, guard

with run(policy="safe", max_cost_usd=1.0) as ctx:
    @guard()
    def expensive_api_call(query: str):
        # Call expensive API
        return call_llm_api(query)
    
    # If total cost exceeds $1.00, subsequent calls will be blocked
    for query in queries:
        expensive_api_call(query)
```

**Why FailCore is needed:**
- Prevent infinite loops from consuming costs
- Set budget limits
- Monitor spending in real-time

---

## When You DON'T Need FailCore

### Pure Reasoning Agents

If your agent only does:
- Text generation
- Data analysis (no writes)
- Information retrieval (read-only)

You may not need FailCore.

### Fully Sandboxed Environments

If you're already running in:
- Docker containers
- Virtual machines
- Fully restricted environments

FailCore is still useful, but lower priority.

### Demo Only

If agents are only used for:
- Proof of concept
- Demonstration purposes
- Not touching production environments

FailCore may be overkill.

---

## Decision Tree

**Should I use FailCore?**

```
Will the agent perform real-world side effects?
├─ No → May not need FailCore
└─ Yes → Continue

Can these side effects cause damage?
├─ No → May not need FailCore
└─ Yes → Continue

Need audit trails?
├─ No → Consider FailCore (safety guarantees)
└─ Yes → Strongly recommend FailCore

Need cost control?
├─ No → Consider FailCore (safety guarantees)
└─ Yes → Strongly recommend FailCore
```

---

## Summary

If your agent **can cause damage**, FailCore should be in the execution path.

FailCore provides:
- ✅ Execution-time safety guarantees
- ✅ Complete operation tracing
- ✅ Cost control
- ✅ Audit capabilities

**When in doubt, use FailCore.**

---

## Next Steps

- [Installation Guide](../getting-started/install.md)
- [Quick Start](../getting-started/first-run.md)
- [Core Concepts](../concepts/execution-boundary.md)
