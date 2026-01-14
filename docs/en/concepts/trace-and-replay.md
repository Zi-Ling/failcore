# Trace and Replay

FailCore records all execution to trace files, supporting post-analysis and replay.

---

## What is a Trace

A trace is a complete record of the execution process:

- Every tool call
- Policy decisions
- Execution results
- Observed side effects
- Timestamps and performance metrics

Trace files are in JSONL format (one JSON object per line).

---

## Trace File Format

### Event Types

Trace files contain the following event types:

#### STEP_START

Tool call started:

```json
{
  "event": "STEP_START",
  "step_id": "abc123",
  "tool": "write_file",
  "params": {"path": "test.txt", "content": "Hello"},
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### POLICY_CHECK

Policy check result:

```json
{
  "event": "POLICY_CHECK",
  "step_id": "abc123",
  "decision": "ALLOW",
  "validator": "security_path_traversal",
  "reason": "Path is within sandbox"
}
```

#### SIDE_EFFECT

Observed side effect:

```json
{
  "event": "SIDE_EFFECT",
  "step_id": "abc123",
  "type": "filesystem.write",
  "target": "test.txt",
  "category": "filesystem"
}
```

#### STEP_END

Tool call ended:

```json
{
  "event": "STEP_END",
  "step_id": "abc123",
  "status": "SUCCESS",
  "output": "Wrote 5 bytes",
  "duration_ms": 12.5
}
```

#### POLICY_DENIED

Policy denial:

```json
{
  "event": "POLICY_DENIED",
  "step_id": "abc123",
  "reason": "Path traversal detected",
  "error_code": "PATH_TRAVERSAL",
  "suggestion": "Use relative paths, don't use '..'"
}
```

---

## Trace File Location

By default, trace files are saved in:

```
<project root>/.failcore/runs/<date>/<run_id>/trace.jsonl
```

### Custom Trace Path

```python
from failcore import run

# Use custom path
with run(trace="my_trace.jsonl") as ctx:
    pass

# Disable tracing
with run(trace=None) as ctx:
    pass
```

---

## View Traces

### CLI Commands

#### List All Traces

```bash
failcore list
```

Output:
```
Run ID                    Date       Status    Steps
abc123...                 2024-01-15 SUCCESS   5
def456...                 2024-01-15 BLOCKED   2
```

#### Show Trace Details

```bash
failcore show <run_id>
```

Or:

```bash
failcore show <trace_file>
```

Shows:
- All steps
- Policy decisions
- Execution results
- Side effects

#### Generate Report

```bash
failcore report <run_id>
```

Generates HTML report including:
- Execution summary
- Timeline
- Violation statistics
- Cost analysis

---

## Replay

Replay allows you to:

1. **Policy Replay**: Re-evaluate historical execution with new policies
2. **Logic Replay**: Zero-cost debugging (don't execute tools)
3. **Deterministic Replay**: Reproducible execution

### Replay Modes

#### REPORT Mode

Audit mode, only reports what would happen:

```bash
failcore replay report <trace_file>
```

Output:
- Which steps would be blocked by new policy
- Which steps would pass
- Policy differences

#### MOCK Mode

Simulation mode, injects historical outputs:

```bash
failcore replay mock <trace_file>
```

Features:
- Don't execute actual tools
- Use historical outputs
- For testing and debugging

### Replay Example

```python
from failcore.core.replay import Replayer, ReplayMode

# Create replayer
replayer = Replayer("trace.jsonl", mode=ReplayMode.REPORT)

# Replay step
result = replayer.replay_step(
    step_id="abc123",
    tool="write_file",
    params={"path": "test.txt", "content": "Hello"},
    fingerprint={"tool": "write_file", "params_hash": "..."}
)

# Check result
if result.hit:
    print(f"Matched historical execution: {result.historical_output}")
else:
    print(f"New execution: {result.current_output}")
```

---

## Trace Analysis

### View Violations

```bash
failcore audit <trace_file>
```

Analyzes trace file, identifies:
- Policy violations
- Side-effect boundary crossings
- Anomaly patterns

### Cost Analysis

```bash
failcore report <trace_file> --include-cost
```

Shows:
- Total cost
- Cost per step
- Cost trends

---

## Trace File Structure

Complete trace file example:

```jsonl
{"event": "RUN_START", "run_id": "abc123", "policy": "fs_safe", "timestamp": "2024-01-15T10:30:00Z"}
{"event": "STEP_START", "step_id": "step1", "tool": "write_file", "params": {"path": "test.txt", "content": "Hello"}}
{"event": "POLICY_CHECK", "step_id": "step1", "decision": "ALLOW", "validator": "security_path_traversal"}
{"event": "SIDE_EFFECT", "step_id": "step1", "type": "filesystem.write", "target": "test.txt"}
{"event": "STEP_END", "step_id": "step1", "status": "SUCCESS", "output": "Wrote 5 bytes", "duration_ms": 12.5}
{"event": "STEP_START", "step_id": "step2", "tool": "write_file", "params": {"path": "../../etc/passwd", "content": "hack"}}
{"event": "POLICY_CHECK", "step_id": "step2", "decision": "DENY", "validator": "security_path_traversal", "reason": "Path traversal detected"}
{"event": "POLICY_DENIED", "step_id": "step2", "error_code": "PATH_TRAVERSAL", "suggestion": "Use relative paths"}
{"event": "STEP_END", "step_id": "step2", "status": "BLOCKED", "duration_ms": 0.5}
{"event": "RUN_END", "run_id": "abc123", "status": "PARTIAL", "total_steps": 2, "blocked_steps": 1}
```

---

## Trace Best Practices

### 1. Preserve Trace Files

Trace files contain complete execution history and should:
- Use version control (encrypt if sensitive)
- Archive regularly
- Set retention policies

### 2. Use Tags

```python
from failcore import run

with run(tags={"env": "production", "version": "1.0"}) as ctx:
    pass
```

Tags are used for filtering and searching traces.

### 3. Regular Review

```bash
# View recent violations
failcore audit --recent

# Generate weekly report
failcore report --since 7d
```

### 4. Replay Testing

Before deploying new policies, use replay testing:

```bash
# Replay historical trace with new policy
failcore replay report <trace_file> --policy new_policy.yaml
```

---

## Trace File Size

Trace files are typically small:

- Per step: ~1-5 KB
- 1000 steps: ~1-5 MB
- Compressed: ~10-20% of original size

For large runs, consider:
- Compressing trace files
- Regularly cleaning old traces
- Using external storage

---

## Trace API

### Programmatic Access

```python
import json

# Read trace file
with open("trace.jsonl", "r") as f:
    for line in f:
        event = json.loads(line)
        if event["event"] == "STEP_END":
            print(f"Step {event['step_id']}: {event['status']}")
```

### Using TraceRepo

```python
from failcore.web.repos.trace_repo import TraceRepo

repo = TraceRepo()
events = repo.load_trace_events("abc123")

for event in events:
    if event["event"] == "POLICY_DENIED":
        print(f"Violation: {event['reason']}")
```

---

## Summary

Trace and replay are core features of FailCore:

- ✅ Complete execution records
- ✅ Policy replay testing
- ✅ Zero-cost debugging
- ✅ Audit and analysis support
- ✅ Cost tracking

---

## Next Steps

- [CLI Tools](../tools/cli.md) - Learn trace-related CLI commands
- [Reports](../tools/reports.md) - How to generate and analyze reports
- [Policy](policy.md) - How to use traces to test policy changes
