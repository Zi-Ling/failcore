# First Run

This guide walks you through your first FailCore program.

---

## Quick Example

Create a simple Python file `demo.py`:

```python
from failcore import run, guard

with run(policy="fs_safe", sandbox="./data", strict=True) as ctx:
    @guard()
    def write_file(path: str, content: str):
        """Write to file"""
        with open(path, "w") as f:
            f.write(content)
    
    # Try to write a file
    try:
        write_file("test.txt", "Hello FailCore!")
        print("✓ Write successful")
    except Exception as e:
        print(f"✗ Blocked: {e}")
    
    # Try to write outside sandbox (will be blocked)
    try:
        write_file("/etc/passwd", "hack")
        print("✗ Unexpected success")
    except Exception as e:
        print(f"✓ Correctly blocked: {type(e).__name__}")
    
    print(f"\nTrace file: {ctx.trace_path}")
```

Run it:

```bash
python demo.py
```

---

## What Happened

### 1. Create Run Context

```python
with run(policy="fs_safe", sandbox="./data", strict=True) as ctx:
```

This creates a FailCore run context:
- `policy="fs_safe"`: Use filesystem safety policy
- `sandbox="./data"`: Restrict operations to `./data` directory
- `strict=True`: Strict mode, violations raise exceptions

### 2. Use @guard() Decorator

```python
@guard()
def write_file(path: str, content: str):
```

The `@guard()` decorator registers the function with FailCore, making it:
- Checked against policy before execution
- Recorded to trace file on all calls
- Blocked on violations

### 3. Execute Tool Call

```python
write_file("test.txt", "Hello FailCore!")
```

When you call a function decorated with `@guard()`:
1. FailCore checks policy (is path within sandbox?)
2. If allowed, executes the function
3. Records result to trace file

### 4. Violation Blocked

```python
write_file("/etc/passwd", "hack")
```

This call will be blocked because:
- `/etc/passwd` is an absolute path
- It's not within the sandbox `./data`
- It violates the `fs_safe` policy

---

## View Trace

After running, you'll see the trace file path:

```
Trace file: .failcore/runs/2024-01-15/abc123/trace.jsonl
```

View trace content:

```bash
failcore show
```

Or:

```bash
cat .failcore/runs/2024-01-15/abc123/trace.jsonl
```

The trace file contains:
- Parameters for each tool call
- Policy decisions
- Execution results
- Timestamps

---

## Alternative Style: Explicit Registration

Besides the `@guard()` decorator, you can also explicitly register tools:

```python
from failcore import run

def write_file(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)

with run(policy="fs_safe", sandbox="./data") as ctx:
    # Register tool
    ctx.tool(write_file)
    
    # Call tool
    ctx.call("write_file", path="test.txt", content="Hello")
```

Both styles have the same functionality—choose what you prefer.

---

## Network Safety Example

```python
from failcore import run, guard
import urllib.request

with run(policy="net_safe") as ctx:
    @guard()
    def fetch_url(url: str) -> str:
        """Fetch URL content"""
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.read().decode('utf-8')[:200]
    
    # This will succeed (public URL)
    try:
        result = fetch_url("https://httpbin.org/get")
        print(f"✓ Success: {result[:50]}...")
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    # This will be blocked (SSRF)
    try:
        result = fetch_url("http://169.254.169.254/latest/meta-data/")
        print("✗ Unexpected success")
    except Exception as e:
        print(f"✓ Correctly blocked SSRF: {type(e).__name__}")
```

---

## Next Steps

- [What Just Happened](what-just-happened.md) - Deep dive into execution flow
- [Core Concepts](../concepts/execution-boundary.md) - Learn about execution boundaries
- [Filesystem Safety](../guides/fs-safety.md) - Filesystem protection guide

---

## Common Questions

### Why do I need the sandbox parameter?

The `sandbox` parameter defines the allowed scope for filesystem operations. Without it, FailCore cannot know which paths are safe.

### What does strict=True mean?

`strict=True` means policy violations will raise exceptions. If set to `False`, violations are logged but don't block execution (observation mode).

### Where is the trace file?

By default, trace files are saved in:
```
<project root>/.failcore/runs/<date>/<run_id>/trace.jsonl
```

You can customize the path using the `trace` parameter.
