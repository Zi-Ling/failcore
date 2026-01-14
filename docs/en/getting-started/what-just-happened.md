# What Just Happened

This guide explains what happens when FailCore executes a tool call.

---

## Execution Flow

When you call a function decorated with `@guard()`, FailCore performs the following steps:

```
1. Tool call request
   ↓
2. Parameter validation
   ↓
3. Policy check
   ↓
4. Side-effect boundary check
   ↓
5. Execute tool
   ↓
6. Record result
   ↓
7. Return result
```

---

## Detailed Steps

### 1. Tool Call Request

```python
write_file("test.txt", "Hello")
```

When you call the function, the `@guard()` decorator intercepts the call:
- Captures function name and parameters
- Creates execution context
- Prepares policy check

### 2. Parameter Validation

FailCore validates:
- Are parameter types correct?
- Are required parameters provided?
- Are parameter values valid?

If validation fails, returns error immediately without executing the tool.

### 3. Policy Check

Based on your specified policy (e.g., `fs_safe`), FailCore checks:

**Filesystem Policy (`fs_safe`)**:
- Is path within sandbox?
- Does it contain path traversal (`..`)?
- Is it an absolute path (if forbidden)?

**Network Policy (`net_safe`)**:
- Does URL point to private IP?
- Is protocol allowed?
- Is it in allowlist?

If policy check fails, execution is **blocked** (BLOCKED), and the tool is not executed.

### 4. Side-Effect Boundary Check

FailCore predicts side effects the tool may produce:
- Filesystem operations (read/write/delete)
- Network requests (egress)
- Process execution

If side effects exceed allowed boundaries, execution is blocked.

### 5. Execute Tool

If all checks pass, the tool function is called:

```python
def write_file(path: str, content: str):
    with open(path, "w") as f:
        f.write(content)
```

The tool executes normally and may succeed or fail.

### 6. Record Result

Whether successful or failed, FailCore records:
- Tool name and parameters
- Policy decisions
- Execution results
- Observed side effects
- Timestamps and performance metrics

Records are saved to the trace file (`.jsonl` format).

### 7. Return Result

If tool succeeds, returns result.  
If tool fails, raises exception.  
If blocked by policy, raises `PolicyDeny` exception.

---

## Execution Result Status

Each tool call has a status:

### ✅ SUCCESS

Tool executed successfully, returns result.

```python
result = write_file("test.txt", "Hello")
# Status: SUCCESS
```

### ❌ BLOCKED

Policy check failed, tool not executed.

```python
try:
    write_file("/etc/passwd", "hack")
except PolicyDeny as e:
    # Status: BLOCKED
    print(f"Blocked: {e}")
```

### ⚠️ FAIL

Tool execution error (not a policy issue).

```python
try:
    write_file("readonly.txt", "data")
except PermissionError as e:
    # Status: FAIL
    print(f"Execution failed: {e}")
```

---

## Trace File Structure

Trace files are in JSONL format (one JSON object per line):

```json
{"event": "STEP_START", "step_id": "abc123", "tool": "write_file", "params": {"path": "test.txt", "content": "Hello"}}
{"event": "POLICY_CHECK", "step_id": "abc123", "decision": "ALLOW"}
{"event": "STEP_END", "step_id": "abc123", "status": "SUCCESS", "output": "..."}
```

Event types include:
- `STEP_START`: Tool call started
- `POLICY_CHECK`: Policy check result
- `SIDE_EFFECT`: Observed side effect
- `STEP_END`: Tool call ended

---

## Policy Decision Flow

Policy checks execute in a fixed order:

```
1. Side-effect boundary gate (fast pre-check)
   ↓
2. Semantic guard (high-confidence malicious pattern detection)
   ↓
3. Taint tracking/DLP (data loss prevention)
   ↓
4. Main policy check (user/system policy)
```

All guards must return `PolicyResult`.  
Only `PolicyStage` decides whether to block (returns `StepResult`).

---

## Example: Complete Flow

```python
from failcore import run, guard

with run(policy="fs_safe", sandbox="./data") as ctx:
    @guard()
    def write_file(path: str, content: str):
        with open(path, "w") as f:
            f.write(content)
        return f"Wrote {len(content)} bytes"
    
    # Call 1: Success
    result1 = write_file("test.txt", "Hello")
    # Flow:
    # 1. Capture call: write_file("test.txt", "Hello")
    # 2. Validate parameters: ✓
    # 3. Policy check: path "test.txt" is within sandbox ✓
    # 4. Side-effect check: file write is within allowed scope ✓
    # 5. Execute: open("test.txt", "w").write("Hello") ✓
    # 6. Record: STEP_END status=SUCCESS
    # 7. Return: "Wrote 5 bytes"
    
    # Call 2: Blocked
    try:
        write_file("/etc/passwd", "hack")
    except PolicyDeny as e:
        pass
    # Flow:
    # 1. Capture call: write_file("/etc/passwd", "hack")
    # 2. Validate parameters: ✓
    # 3. Policy check: path "/etc/passwd" is not within sandbox ✗
    # 4. Block execution, raise PolicyDeny
    # 5. Record: STEP_END status=BLOCKED
    # 6. Tool function not executed
```

---

## Performance Considerations

FailCore's overhead is minimal:

- **Policy checks**: Typically < 1ms
- **Trace recording**: Asynchronous writes, don't block execution
- **Side-effect detection**: Based on static analysis, no runtime overhead

For most applications, FailCore's overhead is negligible.

---

## Next Steps

- [Execution Boundary](../concepts/execution-boundary.md) - Learn how boundaries work
- [Policy](../concepts/policy.md) - Deep dive into policy system
- [Trace and Replay](../concepts/trace-and-replay.md) - How to use trace files
